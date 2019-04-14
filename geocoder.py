#!/usr/bin/env python

import sys, time, requests, json
from util import *

APIKEY_FILE = "apikey.txt"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


# NOTE: The free maximum is 2500 geocode requests/day
MAX_REQUESTS = 40
request_count = 0


def request_geocode(**qry):
    for i in range(3):
        try:
            qry["key"] = apikey
            r = requests.get(GEOCODE_URL, qry)
            break
        except Exception as e:
            sys.stderr.write("\nERROR: geocoder.request_geocode(): '%s'\n" % str(e))
            sys.stderr.flush()
        if i == 2:
            raise MyException("geocoder.request_geocode(): Unable to GET\n\turl: '%s'\n\tquery: '%s'" % (GEOCODE_URL, str(qry)))
    return json.loads(r.text)


def geocode(address):

    results = request_geocode(address=address)
    if "results" not in results.keys():
        sys.stderr.write("No results key!\n")
        sys.exit(1)

    results = results["results"]
    if len(results) == 0:
        return None
    elif len(results) > 1:
        choice = -1
        line = ""
        while choice < 0:
            print "There are %i results:" % len(results)
            for j, r in enumerate(results):
                print "\t(%i) %s" % (j,r["formatted_address"])
            sys.stdout.write("Choose one: ")
            line = sys.stdin.readline()
            if len(line) == 0:
                sys.exit(0)
            try:
                choice = int(line.strip())
                if len(results) <= choice:
                    choice = -1
            except:
                # TODO: rearrange this loop
                break
        return results[choice]
    else:
        return results[0]


def select_result(addr, result):
    loc = result["geometry"]["location"]
    addr["lat"] = float(loc["lat"])
    addr["lng"] = float(loc["lng"])
    addr["formatted_address"] = result["formatted_address"]
    print "[%i] (%f,%f): %s" % (addr["address_id"], addr["lat"], addr["lng"], addr["formatted_address"])



if __name__ == "__main__":

    f = open(APIKEY_FILE, 'r')
    apikey = f.read().strip()
    f.close()

    Addresses = loader("Addresses")
    print "LOADED: %i of %i addresses geocoded" % (len([a for a in Addresses if a["lat"] is not None]), len(Addresses))

    try:
        for addr in Addresses:
            if request_count >= MAX_REQUESTS:
                break
            if addr["lat"] is None or addr["lng"] is None:
                address = "%s %s %s, %s %s" % (addr["street1"], addr["street2"], addr["city"], addr["state"], addr["zipcode"])
                result = geocode(address)
                request_count += 1
                if result is None:
                    while result is None:
                        sys.stderr.write("[%i] No results for address '%s'\r\n\t%s\r\n" % (addr["address_id"], address, str(addr)))
                        sys.stderr.flush()
                        sys.stdout.write("> ")
                        sys.stdout.flush()
                        address = sys.stdin.readline().strip()
                        if len(address) > 0:
                            result = geocode(address)
                            request_count += 1
                            if result is not None:
                                select_result(addr, result)
                                break
                        else:
                            break
                else:
                    select_result(addr, result)
    except Exception as e:
        sys.stderr.write("\r\nERROR: %s\r\n\r\n" % str(e))
        sys.stderr.flush()

    print "\r\nDUMP: %i of %i addresses geocoded\r\n" % (len([a for a in Addresses if a["lat"] is not None]), len(Addresses))
    sys.stdout.write("Save Addresses (y/n)?  ")
    sys.stdout.flush()
    line = sys.stdin.readline()
    if line.strip().lower() in ["y", "ye", "yes", "ok"]:
        dumper("Addresses", Addresses)
