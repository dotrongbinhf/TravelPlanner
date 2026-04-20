"""
Google Maps Platform Tools — Places API (New).

Uses the Places API (New) endpoints with field masks for cost optimization:
- Text Search (New):   POST places:searchText
- Place Details (New): GET  places/{placeId}
- Nearby Search (New): POST places:searchNearby
- Distance Matrix:     unchanged (not part of Places API)

Reference: https://developers.google.com/maps/documentation/places/web-service
"""

import logging
from typing import Any, Optional
from langchain_core.tools import tool
import httpx
from src.config import settings

logger = logging.getLogger(__name__)

PLACES_API_BASE = "https://places.googleapis.com/v1"

# ROUTE_MATRIX_MOCK = [{'originIndex': 9, 'destinationIndex': 9, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 7, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 1, 'status': {}, 'duration': '598s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 3, 'status': {}, 'duration': '606s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 7, 'status': {}, 'duration': '755s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 2, 'status': {}, 'duration': '765s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 6, 'status': {}, 'duration': '785s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 8, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 0, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 3, 'status': {}, 'duration': '519s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 8, 'status': {}, 'duration': '370s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 4, 'status': {}, 'duration': '419s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 9, 'status': {}, 'duration': '463s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 2, 'status': {}, 'duration': '717s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 3, 'status': {}, 'duration': '468s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 1, 'status': {}, 'duration': '647s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 6, 'status': {}, 'duration': '737s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 1, 'status': {}, 'duration': '197s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 2, 'status': {}, 'duration': '202s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 8, 'status': {}, 'duration': '618s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 7, 'status': {}, 'duration': '706s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 1, 'status': {}, 'duration': '316s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 0, 'status': {}, 'duration': '2159s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 5, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 9, 'status': {}, 'duration': '674s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 8, 'status': {}, 'duration': '312s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 5, 'status': {}, 'duration': '1367s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 6, 'status': {}, 'duration': '222s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 5, 'status': {}, 'duration': '1101s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 4, 'status': {}, 'duration': '732s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 8, 'status': {}, 'duration': '678s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 4, 'status': {}, 'duration': '399s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 9, 'status': {}, 'duration': '713s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 5, 'status': {}, 'duration': '1021s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 6, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 3, 'status': {}, 'duration': '595s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 6, 'status': {}, 'duration': '875s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 7, 'status': {}, 'duration': '813s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 2, 'status': {}, 'duration': '123s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 3, 'status': {}, 'duration': '541s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 3, 'status': {}, 'duration': '981s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 2, 'status': {}, 'duration': '2714s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 7, 'status': {}, 'duration': '605s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 5, 'status': {}, 'duration': '1039s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 9, 'status': {}, 'duration': '1119s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 7, 'status': {}, 'duration': '845s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 7, 'status': {}, 'duration': '119s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 2, 'status': {}, 'duration': '855s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 2, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 8, 'status': {}, 'duration': '600s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 9, 'status': {}, 'duration': '895s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 1, 'status': {}, 'duration': '562s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 4, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 1, 'status': {}, 'duration': '2596s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 1, 'status': {}, 'duration': '437s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 4, 'status': {}, 'duration': '792s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 6, 'status': {}, 'duration': '1528s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 2, 'status': {}, 'duration': '823s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 3, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 8, 'status': {}, 'duration': '484s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 3, 'status': {}, 'duration': '297s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 5, 'status': {}, 'duration': '1351s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 0, 'status': {}, 'duration': '1907s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 6, 'status': {}, 'duration': '636s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 9, 'status': {}, 'duration': '680s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 2, 'status': {}, 'duration': '304s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 6, 'status': {}, 'duration': '843s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 6, 'status': {}, 'duration': '324s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 0, 'status': {}, 'duration': '2393s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 4, 'status': {}, 'duration': '714s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 3, 'status': {}, 'duration': '458s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 5, 'status': {}, 'duration': '899s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 1, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 9, 'status': {}, 'duration': '516s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 2, 'status': {}, 'duration': '1507s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 9, 'status': {}, 'duration': '715s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 5, 'status': {}, 'duration': '1932s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 7, 'status': {}, 'duration': '1497s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 8, 'status': {}, 'duration': '1113s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 1, 'status': {}, 'duration': '526s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 9, 'status': {}, 'duration': '2103s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 6, 'status': {}, 'duration': '2734s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 0, 'status': {}, 'duration': '2245s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 8, 'status': {}, 'duration': '434s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 5, 'status': {}, 'duration': '1233s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 0, 'status': {}, 'duration': '2462s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 0, 'status': {}, 'duration': '2665s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 1, 'status': {}, 'duration': '1294s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 0, 'status': {}, 'duration': '2298s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 4, 'status': {}, 'duration': '598s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 8, 'status': {}, 'duration': '2473s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 0, 'status': {}, 'duration': '2396s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 4, 'status': {}, 'duration': '2378s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 3, 'status': {}, 'duration': '2533s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 7, 'status': {}, 'duration': '2703s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 5, 'status': {}, 'duration': '1428s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 4, 'status': {}, 'duration': '437s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 7, 'status': {}, 'duration': '293s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 0, 'status': {}, 'duration': '2355s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 4, 'status': {}, 'duration': '953s', 'condition': 'ROUTE_EXISTS'}]
ROUTE_MATRIX_MOCK = [{'originIndex': 10, 'destinationIndex': 10, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 3, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 10, 'status': {}, 'duration': '1692s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 11, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 8, 'status': {}, 'duration': '1412s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 9, 'status': {}, 'duration': '1715s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 6, 'status': {}, 'duration': '4382s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 8, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 9, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 8, 'status': {}, 'duration': '2499s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 10, 'status': {}, 'duration': '2533s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 7, 'status': {}, 'duration': '1598s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 9, 'status': {}, 'duration': '1372s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 6, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 7, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 6, 'status': {}, 'duration': '3929s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 6, 'status': {}, 'duration': '978s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 5, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 6, 'status': {}, 'duration': '2530s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 7, 'status': {}, 'duration': '997s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 7, 'status': {}, 'duration': '4085s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 8, 'status': {}, 'duration': '2586s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 8, 'status': {}, 'duration': '1621s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 9, 'status': {}, 'duration': '2938s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 4, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 7, 'status': {}, 'duration': '2998s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 10, 'status': {}, 'duration': '4414s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 3, 'status': {}, 'duration': '1882s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 4, 'status': {}, 'duration': '9421s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 10, 'status': {}, 'duration': '4099s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 0, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 9, 'status': {}, 'duration': '3903s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 2, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 1, 'status': {}, 'duration': '5860s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 1, 'status': {}, 'duration': '459s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 3, 'status': {}, 'duration': '10526s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 5, 'status': {}, 'duration': '8325s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 1, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 4, 'status': {}, 'duration': '10550s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 4, 'status': {}, 'duration': '7599s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 4, 'status': {}, 'duration': '6621s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 0, 'status': {}, 'duration': '445s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 3, 'status': {}, 'duration': '11655s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 6, 'status': {}, 'duration': '6783s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 0, 'status': {}, 'duration': '12049s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 7, 'status': {}, 'duration': '7780s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 1, 'status': {}, 'duration': '11704s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 3, 'status': {}, 'duration': '7725s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 1, 'status': {}, 'duration': '12682s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 0, 'status': {}, 'duration': '6205s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 8, 'status': {}, 'duration': '9370s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 1, 'status': {}, 'duration': '3978s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 3, 'status': {}, 'duration': '10255s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 6, 'status': {}, 'duration': '7939s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 0, 'status': {}, 'duration': '4324s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 0, 'status': {}, 'duration': '14849s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 10, 'status': {}, 'duration': '10710s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 0, 'status': {}, 'duration': '15978s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 4, 'status': {}, 'duration': '6254s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 3, 'status': {}, 'duration': '4366s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 9, 'status': {}, 'duration': '10686s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 9, 'status': {}, 'duration': '11842s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 10, 'status': {}, 'duration': '9554s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 3, 'status': {}, 'duration': '8704s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 1, 'status': {}, 'duration': '14614s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 4, 'status': {}, 'duration': '5906s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 4, 'status': {}, 'duration': '9151s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 0, 'status': {}, 'duration': '14579s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 3, 'status': {}, 'duration': '4017s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 11, 'status': {}, 'duration': '8266s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 1, 'status': {}, 'duration': '14234s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 1, 'status': {}, 'duration': '15633s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 8, 'status': {}, 'duration': '10526s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 7, 'status': {}, 'duration': '8936s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 7, 'status': {}, 'duration': '12954s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 8, 'status': {}, 'duration': '14891s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 4, 'status': {}, 'duration': '1888s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 6, 'status': {}, 'duration': '12305s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 9, 'status': {}, 'duration': '15860s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 9, 'status': {}, 'duration': '16208s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 8, 'status': {}, 'duration': '14543s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 6, 'status': {}, 'duration': '11957s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 7, 'status': {}, 'duration': '13302s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 1, 'status': {}, 'duration': '20237s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 10, 'status': {}, 'duration': '15026s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 10, 'status': {}, 'duration': '14671s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 5, 'status': {}, 'duration': '20256s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 5, 'status': {}, 'duration': '32450s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 5, 'status': {}, 'duration': '34141s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 0, 'status': {}, 'duration': '19850s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 5, 'status': {}, 'duration': '32838s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 10, 'status': {}, 'duration': '32704s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 5, 'status': {}, 'duration': '26016s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 4, 'status': {}, 'duration': '31044s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 8, 'status': {}, 'duration': '39681s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 5, 'status': {}, 'duration': '24135s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 3, 'status': {}, 'duration': '24144s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 3, 'status': {}, 'duration': '29156s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 10, 'status': {}, 'duration': '38045s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 1, 'status': {}, 'duration': '25249s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 9, 'status': {}, 'duration': '34419s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 11, 'status': {}, 'duration': '24644s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 5, 'status': {}, 'duration': '19879s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 2, 'status': {}, 'duration': '42979s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 11, 'status': {}, 'duration': '37603s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 4, 'status': {}, 'duration': '26032s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 11, 'status': {}, 'duration': '28900s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 5, 'status': {}, 'duration': '31860s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 11, 'status': {}, 'duration': '39155s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 11, 'status': {}, 'duration': '36625s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 6, 'status': {}, 'duration': '32083s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 7, 'status': {}, 'duration': '33081s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 8, 'status': {}, 'duration': '34670s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 0, 'status': {}, 'duration': '24862s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 11, 'status': {}, 'duration': '39360s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 0, 'status': {}, 'duration': '13027s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 11, 'status': {}, 'duration': '30781s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 11, 'status': {}, 'duration': '43161s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 11, 'status': {}, 'duration': '37668s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 6, 'status': {}, 'duration': '37095s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 2, 'status': {}, 'duration': '49191s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 5, 'status': {}, 'duration': '49343s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 11, 'status': {}, 'duration': '25021s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 0, 'status': {}, 'duration': '65880s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 7, 'status': {}, 'duration': '79110s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 10, 'destinationIndex': 2, 'status': {}, 'duration': '78594s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 5, 'status': {}, 'duration': '34390s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 9, 'status': {}, 'duration': '39761s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 2, 'status': {}, 'duration': '69826s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 3, 'status': {}, 'duration': '70174s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 2, 'status': {}, 'duration': '71707s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 2, 'status': {}, 'duration': '77551s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 2, 'status': {}, 'duration': '80286s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 11, 'destinationIndex': 7, 'status': {}, 'duration': '38092s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 2, 'status': {}, 'duration': '65947s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 9, 'status': {}, 'duration': '80779s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 1, 'status': {}, 'duration': '66267s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 8, 'status': {}, 'duration': '80700s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 2, 'status': {}, 'duration': '80081s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 4, 'status': {}, 'duration': '72062s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 10, 'status': {}, 'duration': '79064s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 2, 'status': {}, 'duration': '65570s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 6, 'status': {}, 'duration': '78113s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 2, 'status': {}, 'duration': '78529s', 'condition': 'ROUTE_EXISTS'}]

def _places_headers(field_mask: str) -> dict[str, str]:
    """Build headers for Places API (New) requests."""
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
        "X-Goog-FieldMask": field_mask,
    }


# ============================================================================
# TEXT SEARCH (New)
# POST https://places.googleapis.com/v1/places:searchText
# ============================================================================

@tool
async def places_text_search_id_only(
    query: str,
    location_bias: Optional[str] = None,
) -> list[dict[str, str]]:
    """Search for places by text query and return only Place IDs (Places API New).
    
    This is the first step in the Place Resolution Pipeline:
    1. Search by name → get PlaceId
    2. Use PlaceId[0] (highest relevance) for DB lookup
    
    Args:
        query: Place name or search text (e.g. "Ba Na Hills Da Nang", "Pho 2000 Ho Chi Minh").
        location_bias: Optional location bias as "lat,lng" to prefer results near this location.

    Returns:
        List of places with placeId and name, ordered by relevance.
    """
    logger.info(f"[places_text_search] query='{query}'")
    try:
        body: dict[str, Any] = {"textQuery": query, "pageSize": 5}

        if location_bias:
            parts = location_bias.split(",")
            if len(parts) == 2:
                body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": float(parts[0]), "longitude": float(parts[1])},
                        "radius": 50000.0,
                    }
                }

        # field_mask = "places.id,places.displayName,places.formattedAddress,places.types"
        field_mask = "places.id"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{PLACES_API_BASE}/places:searchText",
                json=body,
                headers=_places_headers(field_mask),
            )
            resp.raise_for_status()
            data = resp.json()

        places = []
        for p in data.get("places", []):
            display_name = p.get("displayName", {})
            places.append({
                "place_id": p.get("id", ""),
                # "name": display_name.get("text", ""),
                # "address": p.get("formattedAddress", ""),
                # "types": ",".join(p.get("types", [])),
            })

        logger.info(f"[places_text_search] found {len(places)} results")
        return places
    except Exception as e:
        logger.error(f"[places_text_search] error: {e}")
        return [{"error": str(e)}]


@tool
async def places_text_search_full(
    query: str,
    location_bias: Optional[str] = None,
    USE_ENTERPRISE_FIELDS: bool = False,
    page_size: int = 5,
) -> list[dict[str, Any]]:
    """Search for places by text query and return full details.
    Used for Standalone Area Search when no coordinates are available.
    """
    logger.info(f"[places_text_search_full] query='{query}'")
    try:
        body: dict[str, Any] = {"textQuery": query, "pageSize": page_size}

        if location_bias:
            parts = location_bias.split(",")
            if len(parts) == 2:
                body["locationBias"] = {
                    "circle": {
                        "center": {"latitude": float(parts[0]), "longitude": float(parts[1])},
                        "radius": 50000.0,
                    }
                }

        field_mask = _FIELD_MASK_ENTERPRISE if USE_ENTERPRISE_FIELDS else _FIELD_MASK_PRO

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{PLACES_API_BASE}/places:searchText",
                json=body,
                headers=_places_headers(field_mask),
            )
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        if places:
            results = _parse_restaurant_results(places)
            logger.info(f"[places_text_search_full] found {len(results)} results")
            return results
            
        return []
    except Exception as e:
        logger.error(f"[places_text_search_full] error: {e}")
        return []


# ============================================================================
# RESTAURANT SEARCH (LangChain @tool — visible in LangSmith)
# Uses Text Search (New) with locationRestriction (rectangle) + includedType
# ============================================================================

# Toggle to switch between Pro (free 5000/mo) and Enterprise (free 1000/mo) field masks
_FIELD_MASK_PRO = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.primaryType", "places.businessStatus",
])

_FIELD_MASK_ENTERPRISE = ",".join([
    "places.id", "places.displayName", "places.formattedAddress",
    "places.location", "places.primaryType", "places.businessStatus",
    "places.rating", "places.userRatingCount",
    "places.regularOpeningHours", "places.priceLevel",
])

# Fallback chain config: (radius_meters, use_original_query)
_FALLBACK_CHAIN = [
    (1000, True),   # Level 0: original query + 1000m
    (2000, True),   # Level 1: original query + 2000m
    (1000, False),  # Level 2: "restaurant" + 1000m
    (2000, False),  # Level 3: "restaurant" + 2000m
]

import math

def _radius_to_rectangle(lat: float, lng: float, radius_m: float) -> dict:
    """Convert center + radius (meters) to a rectangle (bounding box) for locationRestriction.

    Text Search (New) only supports rectangle for locationRestriction, NOT circle.
    Approximates using 1 degree ≈ 111320m for latitude.
    """
    lat_delta = radius_m / 111320.0
    lng_delta = radius_m / (111320.0 * math.cos(math.radians(lat)))

    return {
        "rectangle": {
            "low": {
                "latitude": lat - lat_delta,
                "longitude": lng - lng_delta,
            },
            "high": {
                "latitude": lat + lat_delta,
                "longitude": lng + lng_delta,
            },
        }
    }


@tool
async def search_restaurants_for_meal(
    query: str,
    lat: float,
    lng: float,
    USE_ENTERPRISE_FIELDS: bool = False,
    page_size: int = 5,
) -> list[dict]:
    """Search for restaurants near a location using Google Places Text Search with fallback chain.

    Tries progressively broader searches until results are found:
    Level 0: original query + 1000m radius
    Level 1: original query + 2000m radius
    Level 2: "restaurant" + 1000m radius
    Level 3: "restaurant" + 2000m radius

    Args:
        query: Search query from meal plan (e.g., "Vietnamese traditional restaurant")
        lat: Latitude of the nearby attraction
        lng: Longitude of the nearby attraction
        page_size: Max results per search (default 5)

    Returns:
        List of restaurant dicts with place details, or empty list if nothing found.
    """
    field_mask = _FIELD_MASK_ENTERPRISE if USE_ENTERPRISE_FIELDS else _FIELD_MASK_PRO

    for level, (radius, use_original) in enumerate(_FALLBACK_CHAIN):
        search_query = query if use_original else "restaurant"
        logger.info(
            f"[restaurant_search] Level {level}: query='{search_query}', "
            f"center=({lat:.4f},{lng:.4f}), radius={radius}m"
        )

        body = {
            "textQuery": search_query,
            "pageSize": page_size,
            "includedType": "restaurant",
            "locationRestriction": _radius_to_rectangle(lat, lng, radius),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{PLACES_API_BASE}/places:searchText",
                    json=body,
                    headers=_places_headers(field_mask),
                )
                resp.raise_for_status()
                data = resp.json()

            places = data.get("places", [])
            if places:
                results = _parse_restaurant_results(places)
                logger.info(
                    f"[restaurant_search] Level {level}: found {len(results)} restaurants"
                )
                return results

            logger.info(f"[restaurant_search] Level {level}: 0 results, trying next")

        except Exception as e:
            logger.error(f"[restaurant_search] Level {level} error: {e}")
            continue

    logger.warning("[restaurant_search] All fallback levels exhausted, no results")
    return []


def _parse_restaurant_results(places: list[dict]) -> list[dict]:
    """Parse raw Places API response into clean restaurant dicts."""
    results = []
    for p in places:
        display_name = p.get("displayName", {})
        location = p.get("location", {})

        # Parse opening hours text (weekdayDescriptions) if available
        reg_hours = p.get("regularOpeningHours", {})
        opening_hours_text = reg_hours.get("weekdayDescriptions", [])

        result = {
            "place_id": p.get("id", "").replace("places/", ""),
            "name": display_name.get("text", ""),
            "address": p.get("formattedAddress", ""),
            "lat": location.get("latitude", 0),
            "lng": location.get("longitude", 0),
            "primary_type": p.get("primaryType", ""),
            "business_status": p.get("businessStatus", ""),
        }

        # Enterprise fields (may not be present if USE_ENTERPRISE_FIELDS=False)
        if "rating" in p:
            result["rating"] = p["rating"]
        if "userRatingCount" in p:
            result["user_ratings_total"] = p["userRatingCount"]
        if "priceLevel" in p:
            result["price_level"] = p["priceLevel"]
        if opening_hours_text:
            result["opening_hours"] = opening_hours_text

        results.append(result)

    return results


# ============================================================================
# PLACE DETAILS (New)
# GET https://places.googleapis.com/v1/places/{placeId}
# ============================================================================

@tool
async def get_google_place_details(place_id: str) -> dict[str, Any]:
    """Get detailed information about a place from Google Places API (New).
    
    This is used in the ensure-place fallback: when a place is NOT found
    in the database, we fetch its details from Google and save it.
    
    Args:
        place_id: Google Place ID.

    Returns:
        Place details including name, address, location, opening hours, rating, etc.
    """
    logger.info(f"[place_details] placeId={place_id}")
    try:
        field_mask = ",".join([
            "id", "displayName", "formattedAddress", "location",
            "types", "rating", "userRatingCount", "regularOpeningHours",
            "websiteUri", "googleMapsUri",
        ])

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{PLACES_API_BASE}/places/{place_id}",
                headers=_places_headers(field_mask),
            )
            resp.raise_for_status()
            result = resp.json()

        # Parse location
        location = result.get("location", {})
        lat = location.get("latitude", 0)
        lng = location.get("longitude", 0)

        # Parse opening hours
        open_hours: dict[str, list[str]] = {
            "monday": [], "tuesday": [], "wednesday": [],
            "thursday": [], "friday": [], "saturday": [], "sunday": [],
        }
        day_keys = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]

        reg_hours = result.get("regularOpeningHours", {})
        for period in reg_hours.get("periods", []):
            open_info = period.get("open", {})
            close_info = period.get("close", {})
            if open_info and close_info:
                day_idx = open_info.get("day", 0)
                if 0 <= day_idx < 7:
                    day_key = day_keys[day_idx]
                    oh = open_info.get("hour", 0)
                    om = open_info.get("minute", 0)
                    ch = close_info.get("hour", 23)
                    cm = close_info.get("minute", 59)
                    open_hours[day_key].append(f"{oh:02d}:{om:02d}-{ch:02d}:{cm:02d}")

        # Get category (first type)
        types = result.get("types", [])
        category = types[0] if types else "point_of_interest"

        display_name = result.get("displayName", {})

        place_data = {
            "placeId": result.get("id", place_id),
            "link": result.get("googleMapsUri", f"https://www.google.com/maps/place/?q=place_id:{place_id}"),
            "title": display_name.get("text", ""),
            "category": category,
            "location": {
                "type": "Point",
                "coordinates": [lng, lat],  # GeoJSON: [lng, lat]
            },
            "address": result.get("formattedAddress", ""),
            "openHours": open_hours,
            "website": result.get("websiteUri", ""),
            "reviewCount": result.get("userRatingCount", 0),
            "reviewRating": result.get("rating", 0),
            "reviewsPerRating": {},
            "cid": "",
            "description": "",
            "thumbnail": "https://placehold.co/600x400?text=No+Image",
            "images": [],
            "userReviews": [],
        }

        logger.info(f"[place_details] resolved: {place_data['title']}")
        return place_data
    except Exception as e:
        logger.error(f"[place_details] error: {e}")
        return {"error": str(e)}


# ============================================================================
# NEARBY SEARCH (New)
# POST https://places.googleapis.com/v1/places:searchNearby
# ============================================================================

@tool
async def places_nearby_search(
    lat: float,
    lng: float,
    radius: int = 2000,
    place_type: str = "restaurant",
    keyword: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search for places near a specific location (Places API New).
    
    Args:
        lat: Latitude of the center point.
        lng: Longitude of the center point.
        radius: Search radius in meters (default 2000m = 2km).
        place_type: Google Place type (e.g. "restaurant", "tourist_attraction", "cafe").
        keyword: Optional keyword — if provided, uses Text Search with location bias instead.

    Returns:
        List of nearby places with basic info.
    """
    logger.info(f"[nearby_search] ({lat},{lng}), type={place_type}, keyword={keyword}")
    try:
        # If keyword is provided, use Text Search with location bias (Nearby Search doesn't support keyword)
        if keyword:
            return await _nearby_via_text_search(lat, lng, radius, place_type, keyword)

        body: dict[str, Any] = {
            "includedTypes": [place_type],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
        }

        field_mask = "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types,places.location"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{PLACES_API_BASE}/places:searchNearby",
                json=body,
                headers=_places_headers(field_mask),
            )
            resp.raise_for_status()
            data = resp.json()

        places = []
        for p in data.get("places", []):
            loc = p.get("location", {})
            display_name = p.get("displayName", {})
            places.append({
                "place_id": p.get("id", ""),
                "name": display_name.get("text", ""),
                "address": p.get("formattedAddress", ""),
                "rating": p.get("rating", 0),
                "user_ratings_total": p.get("userRatingCount", 0),
                "types": p.get("types", []),
                "lat": loc.get("latitude", 0),
                "lng": loc.get("longitude", 0),
            })

        logger.info(f"[nearby_search] found {len(places)} nearby places")
        return places
    except Exception as e:
        logger.error(f"[nearby_search] error: {e}")
        return [{"error": str(e)}]


async def _nearby_via_text_search(
    lat: float, lng: float, radius: int, place_type: str, keyword: str
) -> list[dict[str, Any]]:
    """Fallback: use Text Search with location bias when keyword filtering is needed."""
    body: dict[str, Any] = {
        "textQuery": f"{keyword} {place_type}",
        "pageSize": 10,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius),
            }
        },
    }

    field_mask = "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.types,places.location"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{PLACES_API_BASE}/places:searchText",
            json=body,
            headers=_places_headers(field_mask),
        )
        resp.raise_for_status()
        data = resp.json()

    places = []
    for p in data.get("places", []):
        loc = p.get("location", {})
        display_name = p.get("displayName", {})
        places.append({
            "place_id": p.get("id", ""),
            "name": display_name.get("text", ""),
            "address": p.get("formattedAddress", ""),
            "rating": p.get("rating", 0),
            "user_ratings_total": p.get("userRatingCount", 0),
            "types": p.get("types", []),
            "lat": loc.get("latitude", 0),
            "lng": loc.get("longitude", 0),
        })

    return places


# ============================================================================
# ROUTE MATRIX — Internal function for VRP solver
# ============================================================================

# Map local_transportation (from Orchestrator) → Routes API travelMode
LOCAL_TRANSPORT_MAP = {
    "car": "DRIVE",
    "taxi": "DRIVE",
    "motorbike": "TWO_WHEELER",
    "walking": "WALK",
    "bus": "TRANSIT",
    "metro": "TRANSIT",
    "train": "TRANSIT",
}


async def compute_route_matrix(
    locations: list[tuple[float, float]],
    travel_mode: str = "DRIVE",
    chunk_size: int = 25,
) -> list[list[int]]:
    """
    Internal function — compute NxN travel time matrix via Routes API.
    
    Used by VRP solver, NOT exposed as an LLM tool.
    
    Args:
        locations: List of (lat, lng) tuples.
        travel_mode: Routes API travel mode (DRIVE, TWO_WHEELER, WALK, TRANSIT).
        chunk_size: Max origins/destinations per API request (25 = 625 elements max).
        
    Returns:
        NxN matrix of travel durations in minutes.
    """
    n = len(locations)
    if n == 0:
        return []
    
    matrix = [[0] * n for _ in range(n)]
    total_elements = 0
    chunk_count = 0
    
    for i_start in range(0, n, chunk_size):
        i_end = min(i_start + chunk_size, n)
        
        for j_start in range(0, n, chunk_size):
            j_end = min(j_start + chunk_size, n)
            
            origins = [
                {
                    "waypoint": {
                        "location": {
                            "latLng": {"latitude": locations[i][0], "longitude": locations[i][1]}
                        }
                    }
                }
                for i in range(i_start, i_end)
            ]
            
            destinations = [
                {
                    "waypoint": {
                        "location": {
                            "latLng": {"latitude": locations[j][0], "longitude": locations[j][1]}
                        }
                    }
                }
                for j in range(j_start, j_end)
            ]
            
            num_elements = len(origins) * len(destinations)
            total_elements += num_elements
            chunk_count += 1
            
            body = {
                "origins": origins,
                "destinations": destinations,
                "travelMode": travel_mode,
            }
            
            logger.info(
                f"[route_matrix_internal] Chunk #{chunk_count}: "
                f"{len(origins)}x{len(destinations)} = {num_elements} elements "
                f"(travelMode: {travel_mode})"
            )
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                        json=body,
                        headers=_places_headers(
                            "originIndex,destinationIndex,duration,status,condition"
                        ),
                    )
                    resp.raise_for_status()
                    elements = resp.json()
                    logger.info(f"[route_matrix_internal] Chunk #{chunk_count}: {elements}")

                # MOCK_HERE
                # elements = ROUTE_MATRIX_MOCK

                for elem in elements:
                    oi = elem.get("originIndex", 0)
                    di = elem.get("destinationIndex", 0)
                    condition = elem.get("condition", "")
                    
                    if condition == "ROUTE_EXISTS":
                        dur_str = elem.get("duration", "0s")
                        dur_seconds = int(dur_str.rstrip("s")) if dur_str else 0
                        matrix[i_start + oi][j_start + di] = dur_seconds // 60
                    else:
                        matrix[i_start + oi][j_start + di] = 9999
                        
            except Exception as e:
                logger.error(f"[route_matrix_internal] Chunk #{chunk_count} error: {e}")
                # Fill with fallback Euclidean for this chunk
                import math
                for i in range(i_start, i_end):
                    for j in range(j_start, j_end):
                        if i != j:
                            dist = math.hypot(
                                (locations[i][0] - locations[j][0]) * 111,
                                (locations[i][1] - locations[j][1]) * 111
                                * math.cos(math.radians(locations[i][0])),
                            )
                            matrix[i][j] = max(5, int(dist / 30 * 60))
    
    logger.info(f"[route_matrix_internal] Total: {total_elements} elements, {chunk_count} chunks")
    return matrix


