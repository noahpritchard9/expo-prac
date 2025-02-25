import osmnx as ox
import geopandas as gpd
import random as rand
import osmium
import requests as r
from communication import communication
from setup import setup
from osmiumUpdates import UpdateMap
from score import score
from setup import setup
from visualize import visualize
import networkx as nx
import json

class run:
    def run(locData, prefData, footwaysSimplified):
        #Get user Location and Preferences
        shade = 0
        PoI = 1
        paved = 1
        lit = 1
        distance = -1
        #prefData = [elevation, PoI, paved, lit, distance]

        shade = prefData[0]
        PoI = prefData[1]
        paved = prefData[2]
        lit = prefData[3]
        distance = prefData[4]
        elevation = 0

        #Here's our walking map which simplifies the map to just the walking paths
        #dist is set by preferences:
        length = 0
        if prefData[-1] == -1:
            length = 804.672    #.5 mile radius, for ~1 mile route
        elif prefData[-1] == 0:
            length = 1207.01    #.75 mile radis, for ~1.5 mile route
        elif prefData[-1] == 1:
            length = 1609.34    #1 mile radius, for ~2 mile route

        #Let's create our general storage for routes:
        startPoint = ox.distance.nearest_nodes(footwaysSimplified, X=locData[1], Y=locData[0])
        #routes = [[Dist, Total score, shade score, PoI score, paved score, lit score, route]]
        routes = [[0,0,0,0,0,0,startPoint]]

        #elevation requires running a different route generator, so we'll differentiate that here:
        if elevation == 1:
            route = run.elevationCalculation(footwaysSimplified)
            return route     
           
        #here we focus on if elevation was not considered
        else:
            ox.settings.all_oneway = False
            ox.settings.log_console = False
            #Use i to determine when we should stop running this code. Looking for half of our points to meet the distance
            i = 0
            iter = 0
            #while loop to tell us what percentage of routes we want to be over the threshold
            while i < len(routes) / 100 and i < 10:
                tempRoutes = []
                #reset i to account for routes this run past distance
                i = 0
                
                #iterate through all saved routes
                for r in routes:
                    #print(r)
                    #if we can add to the route...
                    if r[0] < (length):
                        #look into all of its neighbors
                        for nbr in footwaysSimplified[r[-1]]:
                            numNode = r.count(nbr)
                            if numNode == 1:
                                G = r.copy()
                                tempRoutes.append(G)
                                tempRoutes[-1][1] -= 10
                                tempRoutes[-1].append(nbr)
                                
                                #add in distance
                                tempRoutes[-1][0] += footwaysSimplified[r[-1]][nbr][0]['length']
                            
                            elif numNode > 1:
                                continue

                            else:
                                G = r.copy()
                                tempRoutes.append(G)
                                #Update scores for our various preferences                    
                                score().score(lit, "lit", "yes", nbr, tempRoutes, footwaysSimplified)
                                
                                score().score(paved, "paved", "yes", nbr, tempRoutes, footwaysSimplified)                                    

                                score().score(shade, "shade", "yes", nbr, tempRoutes, footwaysSimplified)

                                score().score(PoI, "PoI", "yes", nbr, tempRoutes, footwaysSimplified, points = 5)

                                tempRoutes[-1].append(nbr)
                                
                                #add in distance
                                tempRoutes[-1][0] += footwaysSimplified[r[-1]][nbr][0]['length']
                                                    
                    else:
                        i += 1
                routes = tempRoutes
                #a print to help us figure out how many routes we want
                print(f"{i} {(len(routes)/100)}")
                iter+=1
                
                #reduce the routing data set
                if iter % 4 == 0:
                    routes.sort(key=lambda x: x[1])
                    routes = routes[round(.75 * len(routes)) : ]
                
            #narrow down space
            routes.sort(key=lambda x: x[1])
            routes = routes[round(.9 * len(routes)) : ]

            # now let's make the route circular in a simple form
            # This will also allow us to evaluate the distance in a simple manner
            for r in routes:
                startDist=r[0]
                #NOTE: r[6] denotes the first node of our actual route. Before this is scoring and dist
                short = ox.shortest_path(footwaysSimplified, r[-1], r[6])
                try:
                    for i in range(len(short)-1):
                        r[0] += footwaysSimplified[short[i]][short[i+1]][0]['length']

                    if len(short) > 1:
                    #NOTE: Changed from 1 to 0 in attempts to get full circular path to return
                        for n in short[0:]:
                            r.append(n)
                    
                    #this part handles the scoring added:
                    #Scoring USED TO BE: 
                    #r[1] += abs((((r[0]-startDist)/(length)) * 5) - 5)
                    #Scoring is now:
                    y = 10  #y represents how fast we want diminish our score
                    k = 20  #k represents our peak score
                    r[1] += k/((abs((1/y)*(r[0]-startDist) - (length))) + 1)
                except TypeError:
                    print('Did not return shortest path')
                #r[0] += nx.shortest_path_length(footwaysSimplified, r[2], r[-1], weight='length')

            finalRoutes = []
            for r in routes:
                if r[0] >= length*1.5:
                    finalRoutes.append(r)
            finalRoutes.sort(key=lambda x: x[1])
            finalRoutes = finalRoutes[round(.75 * len(finalRoutes)) : ]

            #visualize.showBest(tuple(finalRoutes), footwaysSimplified, locData)

            #Send the data back to the API

            returnRoute = []
            for i in range(6, len(finalRoutes[-1])):
                returnRoute.append([footwaysSimplified.nodes[finalRoutes[-1][i]]['y'], footwaysSimplified.nodes[finalRoutes[-1][i]]['x']])
            obj = [{'latitude': x, 'longitude': y} for [x, y] in returnRoute]
            # Total score, shade score, PoI score, paved score, lit score
            score1 = {
                'total': finalRoutes[-1][1],
                'shade': finalRoutes[-1][2],
                'poi': finalRoutes[-1][3],
                'paved': finalRoutes[-1][4],
                'lit': finalRoutes[-1][5],
            }
            
            returnRoute = []
            for i in range(6, len(finalRoutes[-2])):
                returnRoute.append([footwaysSimplified.nodes[finalRoutes[-2][i]]['y'], footwaysSimplified.nodes[finalRoutes[-2][i]]['x']])
            obj2 = [{'latitude': x, 'longitude': y} for [x, y] in returnRoute]
            # Total score, shade score, PoI score, paved score, lit score
            score2 = {
                'total': finalRoutes[-2][1],
                'shade': finalRoutes[-2][2],
                'poi': finalRoutes[-2][3],
                'paved': finalRoutes[-2][4],
                'lit': finalRoutes[-2][5],
            }
            json = {'route1': obj, 'score1': score1, 'route2': obj2, 'score2': score2}
            return json
            #communication().postRoute(json)


    def elevationCalculation(footwaysSimplified):
        #here we calculate routing for elevation
        #If we account for elevation, then we run the following:
        ox.settings.all_oneway = True
        ox.settings.log_console = True
        #First we pull in the dc map
        G = ox.graph_from_xml("dc.osm")
        #Get the elevations
        walk_Map = ox.elevation.add_node_elevations_google(footwaysSimplified, api_key= '')
        #Get the elevation grades
        walk_Map = ox.elevation.add_edge_grades(walk_Map)
        #we've now converted our walking map to consider elevation
        return walk_Map
