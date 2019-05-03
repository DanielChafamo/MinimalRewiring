from django.shortcuts import render
from django.http import JsonResponse 
import json 
import os

 
STATIC_ROOT = os.path.join(os.getcwd(), 'netVis/static/')
 
def Index(request):   
  return render(request, 'netvis/index.html')


def LoadJsoNet(request):
  src = os.path.join(os.getcwd(), 'netVis/static/netvis/traffic/traffic.json')
  context={'traffic_matrix': json.dumps(json.load(open(src)))}
  return JsonResponse(context) 