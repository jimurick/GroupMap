#!/usr/bin/env python2.7

import sys, time
from HTMLParser import HTMLParser
from util import *

urls = {}
urls["geisinger"] = "https://www.geisinger.org"
urls["plan selection"] = urls["geisinger"] + "/health-plan/providersearch"
urls["provider search"] = urls["plan selection"] + "/search-results"
urls["provider details"] = urls["plan selection"] + "/provider-details"

# Tables to be scraped, with columns:
Plans = []            # plan_id, plan_name, plan_code, plan_type, plan_seo_name, provider_search_url
ProviderTypes = []    # provider_type_id, provider_type_name, provider_type_code, provider_supertype
Specialties = []      # specialty_id, specialty_name, specialty_code
Modalities = []       # modality_id, modality_name, modality_code
Searches = []         # search_id, plan_id, provider_type_id, search_url
SearchFieldTypes = [] # field_type_id, field_name, is_input, is_select, is_button, all_options
SearchFields = []     # search_id, field_type_id, required_field*, default_value, field_options
                      #  * True if button field_type_id record is a button


def scrape_plans():

    plan_type_xpath = "//div[@class='main-col']/div[@class='accordion-component']/div"
    tree = get_etree(urls["plan selection"])

    for x in tree.xpath(plan_type_xpath):
        plantype = x.find("label").text.strip()
        for li in x.findall(".//ul/li/a"):
            planname = li.text.strip()
            planurl = urls["geisinger"] + li.get("href")
            plancode, planseo = planurl.split("/")[-2:]
            Plans.append({"plan_id":len(Plans), "plan_type":plantype, 
                            "plan_name":planname, "plan_code":plancode, 
                            "plan_seo_name":planseo, "provider_search_url":planurl})


def scrape_plan_search_urls(plan):

    i_understand_xpath = "//div[@class='noticeAcceptance']/a[@class='noticeAcceptance']"
    provider_type_xpath = "//div[@class='main-col']/div[@class='accordion-component']" \
                            + "/div[@class='information']/div[not(@class)]"
    tree = get_etree(plan["provider_search_url"])
    divs = tree.xpath(provider_type_xpath)

    # Some plan search pages are first sent to a page with a statement and an
    # "I Understand" button you need to click first.
    if len(divs) == 0:
        ok = tree.xpath(i_understand_xpath)
        if len(ok) > 0:
            tree = get_etree(plan["provider_search_url"] + ok[0].get("href"))
            divs = tree.xpath(provider_type_xpath)
        else:
            raise MyException("Couldn't find an 'I Understand' button: %s" % plan["provider_search_url"])

    for d in divs:
        psupertype = d.find("label").text.strip()
        for a in d.findall(".//ul/li/a"):
            ptype = a.text.strip()
            purl = urls["geisinger"] + a.get("href")
            types = [t for t in ProviderTypes if t["provider_supertype"] == psupertype 
                                                and t["provider_type_name"] == ptype]
            if len(types) == 0:
                pnumber, pseo = purl.split("/")[-2:]
                types = [{"provider_type_id":int(pnumber), "provider_type_name":ptype, 
                            "provider_supertype":psupertype, "provider_type_code":pseo}]
                ProviderTypes.append(types[0])
            Searches.append({"search_id":len(Searches), "search_url":purl, 
                                "plan_id":plan["plan_id"], 
                                "provider_type_id":types[0]["provider_type_id"]})


def scrape_search_parameters(search, verbose=False):

    form_xpath = "//form[@method='get' and @action='/health-plan/providersearch/search-results/']"

    tree = get_etree(search["search_url"])
    forms = tree.xpath(form_xpath)
    if len(forms) == 0:
        if verbose:
            print "\nNo <form> elements found in %s" % search["search_url"]
        return
    elif len(forms) > 1:
        raise MyException("%i forms found (1 expected): %s" % (len(forms), search["search_url"]))

    fields = forms[0].xpath(".//div[@class='form-field']")
    buttons = forms[0].xpath(".//div[@class='form-button']")
    if len(buttons) != 1:
        raise MyException("Expected 1 button, found %i: %s" % (len(buttons), search["search_url"]))
    for fld in fields:
        inputs = fld.xpath(".//input[@id]")
        selects = fld.xpath(".//select[@id and option]")
        if len(inputs) + len(selects) != 1:
            raise MyException("Wrong number of inputs/selects in form-field div: %s" % search["search_url"])

    for i in buttons[0].xpath(".//input[@id]"):
        process_input(i, search, required=True, button=True)
    for fld in fields:
        req = len(fld.xpath(".//span[@class='required']")) > 0
        inputs = fld.xpath(".//input[@id]")
        if len(inputs) > 0:
            process_input(inputs[0], search, required=req, button=False)
        else:
            process_select(fld.xpath(".//select[@id and option]")[0], search, req)


def process_input(inp, search, required, button):
    types = [t for t in SearchFieldTypes if t["field_name"] == inp.get("id")]
    if len(types) == 0:
        checkbox = (inp.get("type") == "checkbox")
        types = [{"field_type_id":len(SearchFieldTypes), "field_name":inp.get("id"), 
                    "all_options":None, "is_select":False, "is_button":button,
                    "is_text":(not checkbox and not button), 
                    "is_checkbox":(checkbox and not button)}]
        SearchFieldTypes.append(types[0])
    val = inp.get("value")
    if types[0]["is_checkbox"]:
        val = (str(val).lower() == "true")
    if types[0]["field_name"] == "HealthCarePlanId":
        val = val.lower()
    SearchFields.append({"search_id":search["search_id"], 
                            "field_type_id":types[0]["field_type_id"],
                            "required_field":required, "field_options":None, 
                            "default_value":val})


def process_select(sel, search, required):
    sid = sel.get("id")
    ops = [(o.get("value"), html_unescape(o.text)) for o in sel.xpath("option[@value]") 
                                            if (len(o.get("value")) > 0) or not required]
    types = [t for t in SearchFieldTypes if t["field_name"] == sid and t["is_select"]]
    if len(types) == 0:
        types = [{"field_type_id":len(SearchFieldTypes), "field_name":sid, 
                    "all_options":"&".join([o[0] for o in ops if len(o[0]) > 0]),
                    "is_text":False, "is_checkbox":False, 
                    "is_select":True, "is_button":False}]
        SearchFieldTypes.append(types[0])

    opset = set(types[0]["all_options"].split("&"))
    for o in ops:
        if len(o[0]) > 0 and o[0] not in opset:
            opset.add(o[0])
    types[0]["all_options"] = "&".join(opset)
    SearchFields.append({"search_id":search["search_id"], 
                            "field_type_id":types[0]["field_type_id"],
                            "field_options":"&".join([o[0] for o in ops]), 
                            "required_field":required, "default_value":None})

    if sid == "PhysicianSpecialties":
        vals = set([s["specialty_code"] for s in Specialties])
        for o in ops:
            if len(o[0]) > 0 and o[0] not in vals:
                Specialties.append({"specialty_id":len(Specialties), "specialty_code":o[0], "specialty_name":o[1]})
    elif sid == "Modalities":
        vals = set([m["modality_code"] for m in Modalities])
        for o in ops:
            if len(o[0]) > 0 and o[0] not in vals:
                Modalities.append({"modality_id":len(Modalities), "modality_code":o[0], "modality_name":o[1]})



if __name__ == "__main__":
    
    scrape_plans()
    print "%i plans found. Finding provider searches." % len(Plans)
    for i, plan in enumerate(Plans):
        scrape_plan_search_urls(plan)
        sys.stdout.write(" (%i) " % i)
        sys.stdout.flush()

    print "\nScraping %i results" % len(Searches)
    #Plans = loader("Plans")
    #ProviderTypes = loader("ProviderTypes")
    #Searches = loader("Searches")
    #Modalities = loader("Modalities")
    #Specialties = loader("Specialties")
    for i, search in enumerate(Searches):
        scrape_search_parameters(search, verbose=True)
        sys.stdout.write(" (%i) " % i)
        sys.stdout.flush()
    print ""

    dumper("Plans", Plans)
    dumper("ProviderTypes", ProviderTypes)
    dumper("Searches", Searches)
    dumper("SearchFields", SearchFields)
    dumper("SearchFieldTypes", SearchFieldTypes)
    dumper("Specialties", Specialties)
    dumper("Modalities", Modalities)
