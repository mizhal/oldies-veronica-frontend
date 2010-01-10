#!/bin/python
# -*- encoding: utf-8 -*-
import os
from os.path import join, dirname
import re

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
	'/similar', 'Similar',
	'/content', 'Content',
	'/tags', 'Tags',
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
from veronica.libveronica.config import xapian_news_base
from veronica.libveronica.dao.XapianArticleLoader import XapianArticleLoader
from veronica.libveronica.dao.PostgreSQLArticleLoader import PostgreSQLArticleLoader
from veronica.libveronica.dao.PostgresFeedLoader import PostgresFeedLoader

def replace_acute(string):
	st = string.replace(u'\xe1',u'a') 
	st = st.replace(u'\xe9',u"e") 
	st = st.replace(u'\xed',u"i") 
	st = st.replace(u'\xf3',u"o") 
	st = st.replace(u'\xfa',u"u")
	st = st.replace(u'\xb4',u"")
	return st

se = XapianArticleLoader(xapian_news_base, True)

def decay(now, post_time):
	seconds = now - post_time
	hours = seconds / 3600
	days = hours / 24
	weeks = days / 7
	months = weeks / 4
	
	return seconds > 0 and 1 + 0.2*days + 3*weeks + months**3 or 1

class NewsSearch:
	def GET(self):
		return self.do()
		
	def POST(self):
		return self.do()
	
	def do(self):
		input = web.input(_unicode=False)
		
		try:
			query = input.query
			limit = input.limit
		except:
			return
		
		start = time()
		res = se.getFromQuery(replace_acute(query.decode("utf8")), 0, min(50, int(limit)))
		
		now = calendar.timegm(datetime.now().timetuple())
		_decay = lambda time: decay(now, time)
	
		results0 = [( a.fitness/_decay(a.getFetchUnixTime()), a ) for a in res] 
		results0.sort()
		results0.reverse()
		delay = time() - start
		
		st = time()
		html = render.newstable(title=u"Búsqueda de %s"%input.query.decode("utf8") , articles=[i[1] for i in results0][:int(input.limit)], db_elapsed=delay, start_time=time(), nocontent=True)
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
		res = se.getFromQuery(replace_acute(control_query), 0, 1000)
		
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
		html = render.newstable(title=u"Búsqueda controlada" , articles=[i[1] for i in backsearch.results][:50], db_elapsed=backsearch.delay, start_time=time(), nocontent=True)
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
	
class Similar:
	def GET(self):
		return self.do()

	def do(self):
		input = web.input(_unicode=False)
		art_id = int(input.id)
		
		article = loader.loadById(art_id)
		
		st = time()
		articles = se.getSimilarArticles(article, 20)
		delay = time() - st
		
		st = time()
		html = render.newstable(title=u"Artículos similares a %s"%article.title , articles=articles, db_elapsed=delay, start_time=time(), nocontent=True)
		delay = time() - st
		
		return "".join([html, "Render time %s"%delay])
	
class Content:
	def GET(self):
		return self.do()

	def do(self):	
		input = web.input(_unicode=False)
		art_id = int(input.id)
		
		article = loader.loadById(art_id)
		return article.content
	
## TESAURO DE ETIQUETAS

tags = re.split("\s*,\s*", u"""comics,juegos,
		  política, ingenieria del software,
		  ciencias de la computación, ingeniería de computadores,
		  ingeniería informática, automática digital, electrónica,
		  electricidad de potencia, electricidad, proyectos,
		  cine,sociedad, regulación informática, ingeniería de la web,
		  telecomunicaciones,redes""")

tags.sort()

final = []
for i, t in enumerate(tags): 
	final.append({"Id":i,"Title":t})
	
class Tags:
	def GET(self):
		return self.do()

	def do(self):	
		input = web.input(_unicode=False)
		try:
			prefix = input.prefix
			return simplejson.dumps({"ResultSet":{"Result":filter(lambda x: x.startswith(prefix), final)}})
		except:
			return simplejson.dumps({"ResultSet":{"Result":final}})

##########################
## APLICACION
##########################
application = SessionMiddleware(web.application(urls, globals()).wsgifunc())
