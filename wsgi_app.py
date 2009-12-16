#!/bin/python
# -*- encoding: utf-8 -*-
import os
from os.path import join, dirname

import calendar
from datetime import datetime
from time import time
from threading import Thread, Lock
from Queue import Queue

#######################
## @deps pila web
#######################
import web
from beaker.middleware import SessionMiddleware
from web.contrib.template import render_mako

#######################
## @deps serializacion
#######################
import simplejson

#######################
## Mapa de direcciones - agentes
#######################
urls = (
	'/news.*', 'NewsSearch',
	'/last', 'Last',
	'/lastByFeed.*','LastByFeed',
	'/inbox', 'Inbox',
	'/control', "ControlledSearch",
)

#######################
## Plantillas
#######################
render = render_mako(
        directories=[join(dirname(__file__), 'templates').replace('\\','/'),],
        input_encoding='utf-8',
        output_encoding='utf-8',
        )

#########################
## Dependencias de la libreria veronica
#########################
from veronica.libveronica.utils.html_processing import replace_acute
from veronica.libveronica.config import xapian_news_base
from veronica.libveronica.dao.XapianArticleLoader import XapianArticleLoader
from veronica.libveronica.dao.PostgreSQLArticleLoader import PostgreSQLArticleLoader
from veronica.libveronica.dao.PostgresFeedLoader import PostgresFeedLoader

se = XapianArticleLoader(xapian_news_base, True)

def decay(now, post_time):
	seconds = now - post_time
	hours = seconds / 3600
	days = hours / 24
	weeks = days / 7
	
	return seconds > 0 and 1 + seconds**0.1 + 2*hours + days**2 + weeks**6 or 1

class NewsSearch:
	def GET(self):
		return self.do()
		
	def POST(self):
		return self.do()
	
	def do(self):
		input = web.input(_unicode=False)
		
		start = time()
		res = se.getFromQuery(replace_acute(input.query.decode("utf8")), 0, min(50, int(input.limit)))
		
		now = calendar.timegm(datetime.now().timetuple())
		_decay = lambda time: decay(now, time)
	
		results0 = [( a.fitness/_decay(a.getFetchUnixTime()), a ) for a in res] 
		results0.sort()
		results0.reverse()
		delay = time() - start
		
		st = time()
		html = render.newstable(title=u"Búsqueda de %s"%input.query.decode("utf8") , articles=[i[1] for i in results0][:int(input.limit)], db_elapsed=delay, start_time=time())
		delay = time() - st
			
		return "".join([html, "Render time %s"%delay])
		
control_query = ur"""~tesauro ~thesaurus ~htc ~hero ~android
 ~visualizacion ~visualization ~infographics ~mobile ~portfolio ~logbook ~agent ~based ~systems" ia ai "artificial intelligence" clustering tagging enso ubiquity python pys60 analysis design "the secret world" funcom
~reverse ~engineering ~machine ~learning ~engineering ~ingeniería
"""		

class ControlledSearchBackThread(Thread):
	def __init__(self):
		Thread.__init__(self)
		self.results = []
		self.lock = Lock()
		self.active = True
		self.delay = 0

		start = time()
		res = se.getFromQuery(replace_acute(control_query), 0, 10000)
		
		now = calendar.timegm(datetime.now().timetuple())
		_decay = lambda time: decay(now, time)
	
		results0 = [( a.fitness/_decay(a.getPubUnixTime()), a ) for a in res] 
		results0.sort()
		results0.reverse()
		self.delay = time() - start
		
		self.lock.acquire()
		self.results = results0
		self.lock.release()
		
		self.last_update = datetime.now()
		
	def run(self):
		while self.active:
			try:
				start = time()
				res = se.getFromQuery(replace_acute(control_query), 0, 10000)
			
				now = calendar.timegm(datetime.now().timetuple())
				_decay = lambda time: decay(now, time)
			
				results0 = [( a.fitness/_decay(a.getFetchUnixTime()), a ) for a in res] 
				results0.sort()
				results0.reverse()
				self.delay = time() - start
				
				self.lock.acquire()
				self.results = results0
				self.lock.release()
				
				self.last_update = datetime.now()
			except:
				raise
			
			from time import sleep
			sleep(5*60) ## @todo ajustar al periodo de entrada de noticias
			
	def lockResults(self):
		self.lock.acquire()
	
	def releaseResults(self):
		self.lock.release()
		
backsearch = ControlledSearchBackThread()
backsearch.start()
			
class ControlledSearch:
	def GET(self):
		return self.do()
		
	def POST(self):
		return self.do()
	
	def do(self):
		backsearch.lockResults()
		
		st = time()
		html = render.newstable(title=u"Búsqueda controlada" , articles=[i[1] for i in backsearch.results][:50], db_elapsed=backsearch.delay, start_time=time())
		delay = time() - st
		
		backsearch.releaseResults()
		
		return "".join([html, "Render time %s"%delay, "<br/>:::backend last update: %s"%backsearch.last_update])
		
loader = PostgreSQLArticleLoader()
feed_loader = PostgresFeedLoader()

class Last:
	def GET(self):
		return self.do()
		
	def POST(self):
		return self.do()
	
	def do(self):
		input = web.input(_unicode=False)
		st = time()
		articles = loader.loadLastNArticles(20)
		delay = time() - st
		
		st = time()
		html = render.newstable(title=u"Últimas noticias" , articles=articles, db_elapsed=delay, start_time=time())
		delay = time() - st
		
		return "".join([html, "Render time %s"%delay])
		
class Inbox:
	def GET(self):
		return self.do()
		
	def POST(self):
		return self.do()
	
	def do(self):
		input = web.input(_unicode=False)
		st = time()
		articles = loader.loadLastNArticlesFetched(20)
		delay = time() - st
		
		st = time()
		html = render.newstable(title=u"Bandeja de entrada" , articles=articles, db_elapsed=delay, start_time=time())
		delay = time() - st
		
		return "".join([html, "Render time %s"%delay])

class LastByFeed:
	def GET(self):
		return self.do()
	
	def do(self):
		input = web.input(_unicode=False)
		feed_id = int(input.id)
		
		feed = feed_loader.getById(feed_id)
		
		st = time()
		articles = loader.loadLastNArticlesByFeed(20, feed_id)
		delay = time() - st
		
		st = time()
		html = render.newstable(title=u"Últimas noticias de %s"%feed.title , articles=articles, db_elapsed=delay, start_time=time())
		delay = time() - st
		
		return "".join([html, "Render time %s"%delay])

##########################
## APLICACION
##########################
application = SessionMiddleware(web.application(urls, globals()).wsgifunc())
