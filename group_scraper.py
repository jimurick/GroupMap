#!/usr/bin/env python2.7

import sys, os, time, re, urllib
import threading, Queue
from util import *

# Tables scraped in 'scraper.py':
Plans = []            # plan_id, plan_name, plan_code, plan_type, plan_seo_name, provider_search_url
ProviderTypes = []    # provider_type_id, provider_type_name, provider_type_code, provider_supertype
Specialties = []      # specialty_id, specialty_name, specialty_code
Modalities = []       # modality_id, modality_name, modality_code
Searches = []         # search_id, plan_id, provider_type_id, search_url
SearchFieldTypes = [] # field_type_id, field_name, is_input, is_select, is_button, all_options
SearchFields = []     # search_id, field_type_id, required_field*, default_value, field_options
                      #  * True if button field_type_id record is a button

# PlanGroups records correspond to search results
Addresses = []  # address_id, street1, street2, city, state, zip
Groups = []     # group_id, group_name, group_code
PlanGroups = [] # plan_id, group_id, provenhealth_navigator, handicap_accessible, wheelchair_accessible, extra




class SearchResult:

    DISTANCE_RE = re.compile(r'^\s*(?P<distance>\d+(?:\.\d*)?)\s+mile(?:\(s\))?\s*', re.IGNORECASE)

    def __init__(self, search_result_row_div):

        self.clear()

        heading = search_result_row_div.xpath(".//div[@class='heading']")[0]
        distdivs = heading.xpath("span[@class='distance']")
        strong = heading.xpath("strong")[0]
        details = strong.xpath("span/a")[0]
        ecols = search_result_row_div.xpath(".//div[@class='e-col']")
        labels = ecols[1].xpath("div/span[@class='label']")
        datas = ecols[1].xpath("div/*[@class='data']")

        # heading
        if len(distdivs) > 0:
            self.distance = float(re.match(self.DISTANCE_RE, distdivs[0].text).group("distance"))
        self.name = html_unescape(strong.text.strip())
        self.url_info = map(urllib.unquote_plus, details.get("href").split("/")[4:])
        
        # site/address
        self.address = [html_unescape(s.text.strip()) for s in ecols[0].xpath("span[not(a)]")]
        
        # other info goes into self.data
        for i,label in enumerate(labels):
            l = html_unescape(label.text.strip())
            if len(l) > 1:
                l = l[:-1] if l[-1]==":" else l
                if datas[i].tag == "ul":
                    items = datas[i].xpath("li/span")
                    self.data[l] = [html_unescape(j.text.strip()) for j in items]
                else:
                    self.data[l] = html_unescape(datas[i].text.strip())


    def clear(self):
        self.name = ""
        self.distance = 0.0
        self.address = []
        self.data = {}


    def __str__(self):
        mytuple = (self.name, self.distance, self.url_info, self.address, self.data)
        return "%s (%s miles)\n%s\n%s\n%s" % tuple(map(str, mytuple))



# main functions for threads used in the Search object's search() method, 
# defined below.

def search_page_producer(queue, url, params, page):
    params["Page"] = page
    tree = post_etree(url, params)
    for i, result in enumerate(tree.xpath("//div[contains(@class, 'search-result-row')]")):
        queue.put({"index":(5*(page-1) + i), "result":SearchResult(result)})

def search_page_consumer(queue, doneEvent, resultList):
    while not doneEvent.is_set():
        try:
            r = queue.get(timeout=1)
            resultList[r["index"]] = r["result"]
            queue.task_done()
        except Queue.Empty:
            continue


class Search(object):

    URL = "https://www.geisinger.org/health-plan/providersearch/search-results/"

    THREAD_COUNT = 3

    RESULTS_RE = re.compile(r'^\s*(?P<total>\d+)\s+Result(?:\(s\))?\s+found.\s+Showing\s+results\s+(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*$', re.I)

    def __init__(self):
        self.results = []
        self.params = {}


    def setParams(self, search_id=-1, plan_id=-1, provider_type_id=-1, **kargs):
        self.results = []
        self.params = {}
        if search_id < 0:
            search_id = next(s["search_id"] for s in Searches if s["plan_id"]==int(plan_id)
                                                and s["provider_type_id"]==int(provider_type_id))
        flds = [f for f in SearchFields if f["search_id"] == search_id]
        for f in flds:
            ftype = next(t["field_name"] for t in SearchFieldTypes 
                                        if t["field_type_id"] == f["field_type_id"])
            if f["default_value"] is None:
                self.params[ftype] = ""
            else:
                self.params[ftype] = f["default_value"]
        self.params.update(kargs)


    def search(self, verbose=False):
        self.results = []
        self.params["Page"] = 1
        tree = post_etree(self.URL, self.params)

        # get the total number of search results
        countdivs = tree.xpath("//div[@id='pager-information']")
        if len(countdivs) == 0:
            if verbose:
                print "0 results"
            return
        total, first, last = re.match(self.RESULTS_RE, countdivs[0].text.strip()).groups()
        total = int(total)
        self.results = [None] * total

        # collect the results from the first page
        for i, result in enumerate(tree.xpath("//div[contains(@class, 'search-result-row')]")):
            self.results[i] = SearchResult(result)

        # use threads to download THREAD_COUNT result pages in parallel
        lastPage = (total + 4) / 5
        tc = self.THREAD_COUNT
        queue = Queue.Queue()
        
        # If tc==3, partition [2,...,lastPage] into [[2,3,4],[5,6,7],...]
        for pages in [range(2, lastPage+1)[x:x+tc] for x in xrange(0, lastPage-1, tc)]:
            producers = []
            doneEvent = threading.Event()
            for page in pages:
                producers.append(threading.Thread(target=search_page_producer,
                                                args=(queue, self.URL, self.params.copy(), page)))
                producers[-1].start()
            consumer = threading.Thread(target=search_page_consumer,
                                        args=(queue, doneEvent, self.results))
            consumer.start()
            for t in producers:
                t.join()
            queue.join()
            doneEvent.set()
            consumer.join()


    def __str__(self):
        return "%s\n%s" % (str(self.params), str([r.name for r in self.results]))



class Address:

    CITYSTATEZIP_RE = re.compile(r'^\s*(?P<city>.*),\s+(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:\s*-?\s*\d{4})?)\s*$')
    POBOX_RE = re.compile(r'^\s*(?:PO)?\s+Box\s+(?P<pobox>\d+)\s*$', re.IGNORECASE)
    PHONE_RE = re.compile(r'^\s*\d{3}-\d{3}-\d{4}\s*$')


    def __init__(self):
        self.clear()


    def clear(self):
        self.street1 = self.street2 = self.po_box = self.city = self.state = self.zipcode = self.phone = ""


    def fromList(self, addr):

        self.clear()
        i = 0
        self.street1 = addr[i]
        m = re.match(self.POBOX_RE, addr[i])
        if m:
            self.po_box = m.group("pobox")
        i += 1
        m = re.match(self.POBOX_RE, addr[i])
        if m:
            self.po_box = m.group("pobox")
            self.street2 = addr[i]
            i += 1
            m = re.match(self.CITYSTATEZIP_RE, addr[i])
        else:
            m = re.match(self.CITYSTATEZIP_RE, addr[i])
            if not m:
                self.street2 = addr[i]
                i += 1
                m = re.match(self.CITYSTATEZIP_RE, addr[i])
        if not m:
            self.clear()
            raise MyException("Couldn't find City/State/Zip in first 3 items of array: '%s'" % str(addr))
        self.city, self.state, self.zipcode = re.match(self.CITYSTATEZIP_RE, addr[i]).groups()
        i += 1
        if i < len(addr):
            self.phone = addr[i]
        if i + 1 < len(addr):
            self.clear()
            raise MyException("Unused list item %i in address array: '%s'" % (i+1, str(addr)))


    def findIn(self, table):
        return [a for a in Addresses if a["street1"] == self.street1
                    and a["street2"] == self.street2 and a["po_box"] == self.po_box 
                    and a["city"] == self.city and a["state"] == self.state 
                    and a["zipcode"] == self.zipcode]


    # TODO: ugly
    def toRecord(self, table):
        if len(table) == 0:
            self.address_id = 0
        else:
            self.address_id = table[-1]["address_id"] + 1
        return {"address_id":self.address_id, "street1":self.street1, "street2":self.street2,
                "city":self.city, "po_box":self.po_box, "state":self.state, 
                "zipcode":self.zipcode, "lat":None, "lng":None, "formatted_address":None}



class SearchStats(object):

    LOG_DIR = "logs"

    def __init__(self):
        self.params = { "index":0, "init_time":time.time() }
        self.rows = []
        self.searches = []
        self.overflows = []

    def timeString(self):
        return time.strftime("%Y%m%d%H%M%S", time.localtime(self.params["init_time"]))

    def setParams(self, **kw):
        kw["index"] = self.params["index"] + 1
        kw["init_time"] = self.params["init_time"]
        self.params = kw
        self.params["search_time"] = time.time()
        self.searches.append(self.params.copy())

    def logger(self, **data):
        data.update(self.params)
        data["timestamp"] = time.time()
        self.rows.append(data)

    def overflow(self, zipcode):
        self.overflows.append(zipcode)

    def lastSearch(self):
        if len(self.rows) > 0:
            return [r for r in self.rows if r["index"] == self.params["index"]]
        else:
            return []

    def dump(self, title):
        for srch in self.searches:
            results = [r for r in self.rows if r["index"] == srch["index"]]
            srch["result_count"] = len(results)
            srch["overflow"] = False
            if len(results) == 100:
                srch["overflow"] = (results[-1]["distance"] == 0.0)
        ts = self.timeString()
        dumper("%s-Searches-%s" % (title, ts), self.searches, dirname=self.LOG_DIR)
        dumper("%s-Results-%s" % (title, ts), self.rows, dirname=self.LOG_DIR)
        if len(self.overflows) > 0:
            dumper("%s-Overflows-%s" % (title, ts), self.overflows, dirname=self.LOG_DIR)

    def load(self, searchJson, resultJson):
        self.searches = loader(searchJson)
        self.rows = loader(resultJson)
        if len(self.searches) > 0:
            self.params["index"] = self.searches[-1]["index"]
            self.params["init_time"] = self.searches[-1]["init_time"]
        else:
            self.params["index"] = 0
            self.params["init_time"] = time.time()



class GroupSearchStats(SearchStats):

    def __init__(self):
        super(GroupSearchStats, self).__init__()

    def setParams(self, groupSearch):
        super(GroupSearchStats, self).setParams(
                plan_id=groupSearch.plan_id, 
                source_zip=groupSearch.params["CityOrZipCode"], 
                radius=groupSearch.params["SearchRadius"])

    def logger(self, distance, address, new_address, group, new_group, new_plan_group, new_group_address):
        data = {"distance":distance, "dest_zip":address["zipcode"], 
                "address_id":address["address_id"], "new_address":new_address,
                "group_id":group["group_id"], "new_group":new_group,
                "new_plan_group":new_plan_group, "new_group_address":new_group_address}
        super(GroupSearchStats, self).logger(**data)

    def dump(self):
        super(GroupSearchStats, self).dump("Groups")



class GroupSearch(Search):

    provider_type_id = 21

    def __init__(self):
        self.plan_id = None
        self.plan_code = None
        super(GroupSearch, self).__init__()
        self.stats = GroupSearchStats()


    def dump(self):
        self.stats.dump()

    def load(self, searchJson, resultJson):
        self.stats.load(searchJson=searchJson, resultJson=resultJson)


    def setParams(self, plan_id, CityOrZipCode, SearchRadius):
        self.plan_id = plan_id
        self.plan_code = next(p["plan_code"] for p in Plans if p["plan_id"] == plan_id)
        super(GroupSearch, self).setParams(
                plan_id=plan_id, 
                provider_type_id=GroupSearch.provider_type_id, 
                CityOrZipCode=CityOrZipCode, 
                SearchRadius=SearchRadius)
        self.stats.setParams(self)


    def lastSearchStats(self):
        return self.stats.lastSearch()


    def search(self, verbose=False):

        super(GroupSearch, self).search(verbose)

        if len(self.results) == 100:
            if self.results[-1].distance == 0.0:
                self.stats.overflow(self.params["CityOrZipCode"])

        for result in self.results:

            code = result.url_info[1]
            if result.url_info != [str(GroupSearch.provider_type_id), code, self.plan_code, code]:
                raise MyException("Unexpected url_info: %s\n" % str(result.url_info))
            if result.data["Provider Type"] != "Medical Group or Group Practice":
                raise MyException("Unexpected 'Provider Type': '%s'" % result.data["Provider Type"])

            # TODO: Not sure what all the possibilities are here. For instance,
            #       these could be specific lists instead of just Yes/No's.
            provenhealth = (result.data.get("ProvenHealth Navigator", "No") == "Yes")
            wheelchair = (result.data.get("Wheelchair Accessible", "No") == "Yes")
            handicap = (result.data.get("Handicap Accessible", "No") == "Yes")
            extra = (result.data.get("Extra", "No") == "Yes")

            new_addr = new_group = new_plan_group = new_group_addr = False

            # Get the address and insert a new record into the table if necessary
            addr = Address()
            addr.fromList(result.address)
            addrs = addr.findIn(Addresses)
            if len(addrs) == 0:
                new_addr = True
                addrs = [addr.toRecord(Addresses)]
                Addresses.append(addrs[0])

            # Get the group and insert a new record into the table if necessary
            groups = [g for g in Groups if g["group_code"] == code]
            if len(groups) == 0:
                new_group = True
                groups = [{"group_id":len(Groups), "group_name":result.name, "group_code":code}]
                Groups.append(groups[0])
            
            # Add a record connecting the plan and group if there isn't one
            plangps = [pg for pg in PlanGroups if pg["plan_id"] == self.plan_id
                                            and pg["group_id"] == groups[0]["group_id"]
                                            and pg["address_id"] == addrs[0]["address_id"]]
            if len(plangps) == 0:
                new_plan_group = True
                PlanGroups.append({"plan_id":self.plan_id, "group_id":groups[0]["group_id"],
                                "address_id":addrs[0]["address_id"], "phone":addr.phone,
                                "provenhealth_navigator":provenhealth, "extra":extra,
                                "wheelchair_accessible":wheelchair, "handicap_accessible":handicap})

            self.stats.logger(result.distance, addrs[0], new_addr, groups[0], new_group,
                                new_plan_group, new_group_addr)



class ZipQueue:


    JS_DIR = "state"

    TOSS_RADIUS_LEEWAY = 15.0


    def __init__(self):
        # Start searching with Danville and Atlantic City's zip codes.
        self.queue = [{"zipcode":"17821", "toss_radius":0.0}, {"zipcode":"08401", "toss_radius":0.0}]
        self.used = set()
        self.count = 0


    def empty(self):
        return len(self.queue) == 0

    def currentZip(self):
        return self.queue[0]["zipcode"]

    def currentTossRadius(self):
        return self.queue[0]["toss_radius"]

    def currentSearchCount(self):
        return self.count


    def getStateList(self):
        return list_json(self.JS_DIR)

    def dumpState(self, jsObjName, overwrite=True):
        state = {"queue":self.queue, "used":list(self.used), "count":self.count}
        dumper(jsObjName, state, dirname=self.JS_DIR)

    def loadState(self, jsObjName):
        state = loader(jsObjName, dirname=self.JS_DIR)
        self.queue = state["queue"]
        self.used = set(state["used"])
        self.count = state["count"]


    def update(self, stats, verbose=False):

        self.count += 1
        zipcode = self.queue[0]["zipcode"]
        toss_radius = self.queue[0]["toss_radius"]
        self.queue.pop(0)
        self.used.add(zipcode)

        if verbose:
            sys.stdout.write("[%i results] " % len(stats))

        if len(stats) == 0:
            if verbose:
                print ""
            return

        maxdistance = stats[-1]["distance"]
        if len(stats) == 100 and maxdistance == 0.0:
            sys.stderr.write("\r\nZIP %s: OVERFLOW\r\n" % zipcode)

        # zipmax is a mapping of unused zips to their max distance from the source zip
        zipmax = {}
        for s in stats:
            z = s["dest_zip"]
            if z not in self.used:
                zipmax[z] = max(zipmax.get(z, s["distance"]), s["distance"])

        # Get a list of unused zipcodes, sorted by distance in descending order
        zips = list(zipmax.keys())
        sortafun = lambda x,y: 1 if zipmax[x] < zipmax[y] else (0 if zipmax[x] == zipmax[y] else -1)
        zips.sort(sortafun)

        # These two are only for stdout logging:
        justAdded = []
        justRemoved = []
        # Iterate through the zipcodes, starting with the furthest, to add more to the queue
        for z in zips:
            zInQ = [q for q in self.queue if q["zipcode"] == z]
            if zipmax[z] < toss_radius:
                self.used.add(z)
                if len(zInQ) > 0:
                    justRemoved.append(z)
                    self.queue.remove(zInQ[0])
            elif z not in self.used:
                if len(stats) == 100:
                    tr = stats[-1]["distance"] - zipmax[z] - self.TOSS_RADIUS_LEEWAY
                else:
                    tr = 100 - zipmax[z] - self.TOSS_RADIUS_LEEWAY
                if len(zInQ) > 0:
                    zInQ[0]["toss_radius"] = max(zInQ[0]["toss_radius"], tr)
                else:
                    self.queue.append({"zipcode":z, "toss_radius":tr})
                    justAdded.append(z)
        
        # Pop off any zipcodes that have already been searched
        if len(self.queue) > 0:
            while self.queue[0]["zipcode"] in self.used:
                justRemoved.append(self.queue[0]["zipcode"])
                self.queue.pop(0)
                if len(self.queue) == 0:
                    break

        # log to stdout
        if verbose:
            for z in justAdded:
                sys.stdout.write(" %s " % z)
            print ""
            if len(justRemoved) > 0:
                sys.stdout.write("[tossing out] ")
                for z in justRemoved:
                    sys.stdout.write(" (%s) " % z)
                print ""
            sys.stdout.flush()




if __name__ == "__main__":

    Plans = loader("Plans")
    ProviderTypes = loader("ProviderTypes")
    Searches = loader("Searches")
    SearchFields = loader("SearchFields")
    SearchFieldTypes = loader("SearchFieldTypes")

    if table_exists("Addresses"):
        Addresses = loader("Addresses")
    if table_exists("Groups"):
        Groups = loader("Groups")
    if table_exists("PlanGroups"):
        PlanGroups = loader("PlanGroups")

    # These two parameters were manually changed
    plan_id = 0
    MAX_SEARCHES = 100

    search = GroupSearch()
    queue = ZipQueue()

    states = queue.getStateList()
    if len(states) > 0:
        print "Load state?"
        for i, s in enumerate(states):
            print "(%i) %s" % (i+1, s)
        sys.stdout.write("> ")
        try:
            i = int(sys.stdin.readline())
            if 0 < i <= len(states):
                queue.loadState(states[i-1])
        except:
            print "No state loaded."
            pass

    count = 0
    try:
        while not queue.empty() and count < MAX_SEARCHES:
            count += 1
            print "(%s) SEARCH %i: %i in queue and toss radius %f" % \
                    (queue.currentZip(), queue.currentSearchCount()+1, \
                     len(queue.queue), queue.currentTossRadius())
            search.setParams(plan_id, CityOrZipCode=queue.currentZip(), SearchRadius=100)
            search.search(verbose=False)
            queue.update(search.lastSearchStats(), verbose=True)
    except Exception as e:
        sys.stderr.write("\r\nERROR: %s\r\n\r\n" % str(e))
        sys.stderr.flush()

    sys.stdout.write("Save? (y/n)  ")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line.strip().lower() in ["y", "ye", "yes"]:
    if True:
        if not queue.empty():
            statename = next(p["plan_name"] for p in Plans if p["plan_id"] == plan_id)
            queue.dumpState(statename)
        search.dump()
        dumper("Groups", Groups)
        dumper("Addresses", Addresses)
        dumper("PlanGroups", PlanGroups)
