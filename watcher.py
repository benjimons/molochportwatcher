import sys
import requests
import json
import logging
import syslog
from datetime import date, timedelta

#Variables to be set
queuelimit=100
checkbackdays=21
elastichostname = "http://elastic"
logfile = "logger.log"

#Set up the logging
logging.basicConfig(level=logging.DEBUG, filename=logfile, format='%(asctime)s %(levelname)s %(name)s %(message)s')

#Gather the data from Elasticsearch
def getportdata( date ):
	logging.info("Gathering data for "+str(date))
	r = requests.get(elastichostname+':9200/sessions2-'+str(date)+'/_search', json=data, stream=True)

	#logging.info(r.raw._fp.fp._sock.getpeername())

	response = json.loads(r.text)	
	datalist = { }
	try:
		for hosts in response["aggregations"]["hosts"]["buckets"]:
			portlist = []
			for ports in hosts["ports"]["buckets"]:
				portlist.append(ports["key"])
				syslog.syslog(syslog.LOG_INFO, "Moloch Portwatcher Open Port: "+hosts["key"]+":"+str(ports["key"]))
			datalist[hosts["key"]]=portlist
	except KeyError:
		logging.error("Error: ", exc_info=True) 
		return 0
	logging.info("Gathered data")
	return datalist		

#Compare newest list to older and return only ports that appear in new scan but NOT in old - indicating a new open.
def processlist( listnewest, listoldest ):
	datalist = { }
	for hostname in listnewest:
		i=0
		while i < len(listnewest[hostname]):
			i += 1

			try:
				if listnewest[hostname][i-1] == listoldest[hostname][i-1]:
					logging.debug("Found "+hostname+":"+str(listnewest[hostname][i-1])+" matched "+hostname+":"+str(listoldest[hostname][i-1]))
					continue	
				else:
					logging.debug("moving on")

			except (IndexError, KeyError):	
				#datalist = { }
				portlist = []
				portlist.append(listnewest[hostname][i-1])
				datalist[hostname]=portlist
				logging.debug("Possible new port "+str(hostname)+":"+str(listnewest[hostname][i-1]))
			except:
				logging.error("Error:", exc_info=True)
		
	try:
	    datalist
	except NameError:
	    logging.info("No new ports found")
	    exit(0)
	return datalist


data = {
    "query": {
        "bool": {
            "must_not": [
                {
                    "terms": {
                        "tags": [
                            "acked-unseen-segment-dst"
                        ]
                    }
                }
	    ],
	    "must": [
                {
                    "terms": {
                        "srcMac": [
                            "MAC1", "MAC2"
                        ]
                    }
                },
                {
                    "terms": {
                        "protocol": [
                            "tcp"
                        ]
                    }
                },
                {
                    "terms": {
                        "node": [
                            "NODE1", "NODE2"
                        ]
                    }
                },
                {
                    "range": {
                        "dstPackets": {
                            "gt": "2"
                        }
                    }
                },
                {
                    "range": {
                        "tcpflags.syn-ack": {
                            "gt": "0"
                        }
                    }
                },
                {
                    "range": {
                        "tcpflags.ack": {
                            "gt": "0"
                        }
                    }
                },
                {
                    "range": {
                        "tcpflags.syn": {
                            "gt": "0"
                        }
                    }
                }
            ]
        }
    },
    "from": 0,
    "size": 0,
    "aggs" : {
      "hosts" : {
        "terms" : {
          "field" : "dstIp",
          "size": 10000
        },
        "aggs" : {
          "ports" : {
            "terms" : {
              "field" : "dstPort",
              "min_doc_count": 2
            }
          }
        }
      }
    }
}

#Check how busy the clusre is before starting.
logging.info('Checking cluster health') 
clustertasks = requests.get(elastichostname+':9200/_tasks', stream=True)
logging.info(clustertasks.raw._fp.fp._sock.getpeername())
clustertasks = json.loads(clustertasks.text)
taskcount=0

for node in clustertasks["nodes"]:
	taskcount = taskcount + int(len(clustertasks["nodes"][node]["tasks"]))

logging.info('Found ' + str(taskcount) + " tasks")

if taskcount > queuelimit :
	logging.critical('Too many tasks ('+str(taskcount)+') - the cluster is too busy. Exiting') 
	exit(1)
#
#
#Main routine
#
#

#today = date.today()  - timedelta(days=1)
#print(today)
today = date.today()
d1= today.strftime("%y%m%d")
firstdate = d1

#Get the latest 2 days
list1 = getportdata(firstdate)
if not list1:
        today = date.today() + timedelta(days=-1)
	d1= today.strftime("%y%m%d")
	firstdate = d1
	list1 = getportdata(firstdate)

today2 = today + timedelta(days=-1)
d2 = today2.strftime("%y%m%d")

list2 = getportdata(d2)

newfoundlist = processlist(list1, list2)

#If we found a change between yesterday and today then check back several more days to determine if it existed
i=1
logging.info("Checking back "+str(checkbackdays)+" days for port usage")
while i < checkbackdays:
	today3 = today2 + timedelta(days=-i)
	d3 = today3.strftime("%y%m%d")
	list3 = getportdata(d3)
	i += 1

	newfoundlist = processlist(newfoundlist, list3)
	if len(newfoundlist) == 0:
		break

if len(newfoundlist)>0:
	logging.info("New port found")
	logging.info(newfoundlist)
	for host in newfoundlist:
		for port in newfoundlist[host]:
			#If we get here it means that a port was found, syslog it to Splunk!
			logging.info("Found NEW port, host="+host+" port="+str(port))
			syslog.syslog(syslog.LOG_ERR, "Moloch Portwatcher NEW port, watchernghost="+host+" watcherngport="+str(port))
else:
	logging.info("No new ports found")
	exit(0)

logging.debug("I got to the end!")
