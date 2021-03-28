#  newsstand.py
#  
#  Copyright 2021 TheGinger
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  
#  Hey! It's Ginger here. Just wanted to say that I hope you enjoy NewsStand, and feel free to suggest features on GitHub. Have fun!

VERSION = "0.2.1"

import gi
import newspaper
from easysettings import EasySettings
import threading
import urllib
import favicon
import pickle
import os
import sys
import httplib2
import socket
from time import sleep
import webbrowser
import feedparser
from audioplayer import AudioPlayer
import feedfinder
import openutils
import pidfile
import socket
import argparse
import datetime
parser = argparse.ArgumentParser()
parser.add_argument("file", nargs = "?", default = "__nofile__", help = "Loads a .nsaf file")
parser.add_argument("--exit", help = "Stops NewsStand if it's already running", action="store_true")

settings = EasySettings("/usr/local/lib/newsstand/config/settings.cfg")
sources = EasySettings("/usr/local/lib/newsstand/config/sources.nssl")
_gpidfile = None
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
fileLoadQueue = b""

gi.require_version('AyatanaAppIndicator3', '0.1')
gi.require_version("Gtk", "3.0")
gi.require_version('Notify', '0.7')


from gi.repository import GLib, GObject
from gi.repository import AyatanaAppIndicator3 as AppIndicator, Notify
from gi.repository import Gtk, Gdk, Pango, Gio, GdkPixbuf
from gi.repository.GdkPixbuf import Pixbuf

Notify.init("newsstand")
if not sources.has_option("sources"):
	sources.setsave("sources", {'CNN': 'http://cnn.com', 'Huffington Post': 'http://www.huffingtonpost.com', 'TIME Magazine': 'http://www.time.com', 'BBC': 'http://www.bbc.co.uk', 'ESPN': 'http://espn.com', 'The Guardian': 'http://www.theguardian.com'})
if not settings.has_option("bookmarks"):
	settings.setsave("bookmarks", {"Chuild saevs a stupid": "https://lolz.io", "LEGIT NEWS RIGHT THIS WAE!": "http://cnn.com", "i have super cool idointomn cideis" : "http://cnn.com", "yeetus": "yeetus.io", "what the HELL IS THAT": "aaaaaaaaa"})
if not settings.has_option("subscriptions"):
	settings.setsave("subscriptions", {})

os.chdir(os.path.expanduser("~") + '/Documents/')
try:
    os.makedirs('Articles')
except OSError as e:
	pass
config = newspaper.Config()
config.memoize_articles = False
config.verbose = True


class SimpleThread(threading.Thread):
        def __init__(self, target, daemon = True, startOnInit = True, **args):
                super().__init__(target = target, daemon = daemon, **args)
                if startOnInit:
                        self.start()
        def start(self):
                threading.Thread.start(self)
                while super().is_alive():
                        Gtk.main_iteration()
                        #print(str(super().is_alive()) + super().name)
class SettingsBoxRow(Gtk.ListBoxRow):
	def __init__(self, contentWidget, label = None, labelWidget = None, activatable = False, selectable = False):
		Gtk.ListBoxRow.__init__(self)
		self.activatable = activatable
		self.selectable = selectable
		if label and labelWidget:
			raise ValueError("Cannot specify both label and labelWidget, it has to be one or the other!")
		if label:
			assert isinstance(label, str), "label must be a string!"
			self.label = Gtk.Label(label=label)
		if labelWidget:
			assert isinstance(labelWidget, Gtk.Widget), "labelWidget must be a Gtk.Widget or a subclass of it!"
			self.label = labelWidget
		assert isinstance(contentWidget, Gtk.Widget), "contentWidget must be a Gtk.Widget or a subclass of it!"
		
		self.label.props.xalign = 0
		self.box = Gtk.Box(spacing = 25)
		self.contentWidget = contentWidget
		self.contentWidget.props.valign = Gtk.Align.CENTER
		self.box.pack_start(self.label, True, True, 0)
		self.box.pack_start(self.contentWidget, False, True, 0)
		self.add(self.box)
		self.show_all()

#ORIGINALL UI DONUT STEAL
class Window(Gtk.Window):
	def __init__(self):
		Gtk.Window.__init__(self, title = 'NewsStand', icon_name = "emblem-documents", default_width = 1250, default_height = 750)
		self.set_size_request(1250, 750)
		self.connect("delete-event", lambda w, e: w.hide() or True)
		
		self.source = None
		self.articles = None
		self.articleSelectedName = None
		self.selectedArticle = None
		self.articleImages = []
		self.isLoadingCursor = False
		self.topImage = None
		self.oldArticles = None
		self.newArticles = [{"source": "test source", "title": "Test Article", "url": "http://example.com/rss"}]
		self.sourceFeed = None
		
		self.trayIconMenu = Gtk.Menu()
		self.openMenuItem = Gtk.MenuItem(label = "Open NewsStand")
		self.closeMenuItem = Gtk.MenuItem(label = "Exit NewsStand")
		self.openMenuItem.connect("activate", lambda w: self.show())
		self.closeMenuItem.connect("activate", self.exit)
		self.bookmarksMenu = Gtk.Menu(anchor_hints = Gdk.AnchorHints.RESIZE)
		if len(settings.get("bookmarks")):
			for item in settings.get("bookmarks"):
				self.bookmarksMenu.append(Gtk.MenuItem.new_with_label(label = item))
		self.bookmarksMenuItem = Gtk.MenuItem(label = "Bookmarks...", submenu = self.bookmarksMenu)
		self.trayIconMenu.append(self.openMenuItem)
		self.trayIconMenu.append(self.bookmarksMenuItem)
		self.trayIconMenu.append(self.closeMenuItem)
		self.trayIconMenu.show_all()
		self.trayIcon = AppIndicator.Indicator.new(id = "pyaptify", icon_name = "user-invisible-symbolic", category = AppIndicator.IndicatorCategory.SYSTEM_SERVICES)
		self.trayIcon.props.attention_icon_name = "user-available-symbolic"
		self.trayIcon.set_menu(self.trayIconMenu)
		print("Ignore the criticals, they're normal.")
		self.trayIcon.set_status(AppIndicator.IndicatorStatus.ACTIVE)
		self.subscriptionNotifyChime = AudioPlayer("/usr/local/lib/newsstand/media/notify.mp3")
		self.subscriptionNotifyChime.volume = 50
		self.subscriptionNotification = Notify.Notification.new(summary = "There is a new article available from one of your subscriptions!", icon = "application-rss+xml-symbolic")
		self.subscriptionNotification.connect("closed", self._handleNotificationClose)
		
		self.toplevelBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.contentBox = Gtk.Box()
		self.toplevelBox.add(self.contentBox)
		self.add(self.toplevelBox)
		
		self.articleBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.articlePopover = Gtk.PopoverMenu(constrain_to = Gtk.PopoverConstraint.NONE)
		self.articlePopoverBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.moreItem = Gtk.ModelButton(text = "More about this article")
		self.moreItem.connect("clicked", self.showArticleDetails)
		self.bookmarkItem = Gtk.ModelButton(text = "Bookmark this article")
		self.readingListItem = Gtk.ModelButton(text = "Add to reading list")
		self.openItem = Gtk.ModelButton(text = "Open an article file")
		self.openItem.connect("clicked", self.loadArticleFromFile)
		self.refreshItem = Gtk.ModelButton(text = "Refresh article")
		self.shareItem = Gtk.ModelButton(text = "Share article...", menu_name = "share")
		self.shareMenuBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.shareMenuBack = Gtk.ModelButton(icon = Gio.Icon.new_for_string("go-previous-symbolic"), iconic = True, centered = True, inverted = True, menu_name = "main", relief = Gtk.ReliefStyle.NONE)
		self.saveItem = Gtk.ModelButton(text = "Save to a file")
		self.saveItem.connect("clicked", self.saveArticle)
		self.emailItem = Gtk.ModelButton(text = "Send as an email")
		self.lkItem = Gtk.ModelButton(text = "Post on LinkedIn")
		self.twItem = Gtk.ModelButton(text = "Tweet this article")
		self.pinItem = Gtk.ModelButton(text = "Pin on Pintrest")
		self.lkItem.connect("clicked", lambda w: SimpleThread(self.shareToLK))
		self.twItem.connect("clicked", lambda w: SimpleThread(self.shareToTW))
		self.pinItem.connect("clicked", lambda w: SimpleThread(self.shareToPintrest))
		self.emailItem.connect("clicked", self.shareToEmail)
		self.shareMenuBox.add(self.shareMenuBack)
		self.shareMenuBox.add(self.emailItem)
		self.shareMenuBox.add(self.lkItem)
		self.shareMenuBox.add(self.twItem)
		self.shareMenuBox.add(self.pinItem)
		self.articlePopoverBox.add(self.moreItem)
		self.articlePopoverBox.add(self.bookmarkItem)
		self.articlePopoverBox.add(self.readingListItem)
		self.articlePopoverBox.add(self.refreshItem)
		self.articlePopoverBox.add(self.shareItem)
		self.articlePopoverBox.add(Gtk.Separator.new(orientation = Gtk.Orientation.VERTICAL))
		self.articlePopoverBox.add(self.openItem)
		self.articlePopoverBox.add(self.saveItem)
		self.articlePopover.add(self.articlePopoverBox)
		self.articlePopover.add(self.shareMenuBox)
		self.articlePopover.show_all()
		self.articlePopover.hide()
		self.articlePopover.child_set_property(self.shareMenuBox, "submenu", "share")
		self.articlePopover.props.visible_submenu = "main"
		self.disableArticlePopover()
		
		
		self.articleToolbar = Gtk.ActionBar()
		self.zoomInButton = Gtk.Button.new_from_icon_name("zoom-in-symbolic", Gtk.IconSize.DND)
		self.zoomInButton.connect("clicked", self.increaseFontSize)
		self.zoomOutButton = Gtk.Button.new_from_icon_name("zoom-out-symbolic", Gtk.IconSize.DND)
		self.zoomOutButton.connect("clicked", self.decreaseFontSize)
		self.resetZoomButton = Gtk.Button.new_from_icon_name("zoom-original-symbolic", Gtk.IconSize.DND)
		self.resetZoomButton.connect("clicked", self.resetFontSize)
		self.fullscreenToggleButtonIcon = Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.DND)
		self.fullscreenToggleButton = Gtk.ToggleButton.new()
		self.fullscreenToggleButton.add(self.fullscreenToggleButtonIcon)
		self.articleToolbar.add(self.zoomOutButton)
		self.articleToolbar.add(self.zoomInButton)
		self.articleToolbar.add(self.resetZoomButton)
		self.articleToolbar.pack_end(self.fullscreenToggleButton)
		self.fullscreenToggleButton.connect("toggled", self.toggleFullscreen)
		self.articleLabel = Gtk.Label(label = "No article selected.")
		self.articleToolbar.set_center_widget(self.articleLabel)
		
		self.articleImageGallery = Gtk.FlowBox(selection_mode = Gtk.SelectionMode.NONE)
		self.articleHeaderBox = Gtk.Box(hexpand = True, hexpand_set = True)
		self.articleContentBox = Gtk.Box(expand = True, orientation = Gtk.Orientation.VERTICAL, spacing = 6)
		self.loadingInfoBar = Gtk.InfoBar(revealed = False)
		self.loadingInfoBarLabel = Gtk.Label()
		self.loadingInfoBarSpinner = Gtk.Spinner()
		self.loadingInfoBarSpinner.set_size_request(64, 64)
		self.loadingInfoBarSpinner.start()
		self.loadingInfoBar.get_content_area().add(self.loadingInfoBarSpinner)
		self.loadingInfoBar.get_content_area().add(self.loadingInfoBarLabel)
		self.infoBar = Gtk.InfoBar(show_close_button = True, message_type = Gtk.MessageType.ERROR, revealed = False)
		def _ibCb(widget, response):
			widget.set_revealed(False)
			GLib.timeout_add(100, widget.hide)
		self.infoBar.connect("response", _ibCb)
		self.infoBarLabel = Gtk.Label()
		self.infoBar.get_content_area().add(self.infoBarLabel)
		self.articleBuffer = Gtk.TextBuffer()
		self.centerTag = self.articleBuffer.create_tag("center", justification = Gtk.Justification.CENTER)
		self.fontSizeTag = self.articleBuffer.create_tag("fontSize", scale = 1.0)
		self.articleTextView = Gtk.TextView(buffer = self.articleBuffer, wrap_mode = Gtk.WrapMode.WORD, vexpand = True, vexpand_set = True, margin = 4, cursor_visible = False, editable = False)
		self.articleFrame = Gtk.ScrolledWindow(propagate_natural_height = True, propagate_natural_width = False, margin = 4, overlay_scrolling = False, vexpand = True, vexpand_set = True)#, hscrollbar_policy = Gtk.PolicyType.NEVER)
		self.articleContentBox.add(self.articleTextView)
		self.articleContentBox.add(self.articleImageGallery)
		self.articleFrame.add(self.articleContentBox)
		self.articleSpinner = Gtk.Spinner(halign = Gtk.Align.CENTER, valign = Gtk.Align.CENTER)
		self.articleSpinner.set_size_request(64, 64)
		self.articleTextOverlay = Gtk.Overlay()
		self.articleTextOverlay.add(self.articleFrame)
		self.articleTextOverlay.add_overlay(self.articleSpinner)
		self.articleMenuButtonImage = Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.DND)
		self.articleMenuButton = Gtk.MenuButton(use_popover = True, halign = Gtk.Align.END, popover = self.articlePopover, margin_top = 5)
		self.articleMenuButton.get_style_context().add_class("image-button")
		self.articleMenuButton.add(self.articleMenuButtonImage)
		self.articleListViewToggleButtonImage = Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.DND)
		self.articleListViewToggleButton = Gtk.Button.new()
		self.articleListViewToggleButton.add(self.articleListViewToggleButtonImage)
		self.articleListViewToggleButton.get_style_context().add_class("image-button")
		self.articleListViewToggleButton.props.halign = Gtk.Align.START
		self.articleListViewToggleButton.connect("clicked", self.toggleArticleView)
		#self.articleHeaderBox.pack_start(self.articleLabel, True, True, 0)
		self.articleHeaderBox.pack_start(self.articleListViewToggleButton, False, False, 0)
		self.articleHeaderBox.pack_end(self.articleMenuButton, False, False, 0)
		self.articleBox.add(self.articleHeaderBox)
		self.articleBox.add(self.infoBar)
		self.articleBox.add(self.loadingInfoBar)
		self.articleBox.pack_start(self.articleTextOverlay, True, True, 0)
		self.articleBox.add(self.articleToolbar)
		
		self.sourceConfigPopover = Gtk.Popover()
		self.sourceConfigBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL, expand = True)
		self.sourcesListBox = Gtk.ListBox()
		self.sourcesListBox.set_selection_mode(Gtk.SelectionMode.NONE)
		_sources = sources.get("sources")
		for item in _sources:
			editButton = Gtk.Button.new_from_icon_name("document-edit-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
			editButton.connect("clicked", self.editSource)
			deleteButton = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
			deleteButton.connect("clicked", self.deleteSource)
			deleteButton.get_style_context().add_class("destructive-action")
			buttonBox = Gtk.Box(spacing = 6)
			buttonBox.add(editButton)
			buttonBox.add(deleteButton)
			self.sourcesListBox.add(SettingsBoxRow(buttonBox, label = item))
			if list(_sources).index(item) != len(_sources) - 1:
				self.sourcesListBox.add(Gtk.Separator.new(orientation = Gtk.Orientation.VERTICAL))
		addItemButton = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.LARGE_TOOLBAR)
		addItemButton.connect("clicked", self.addSource)
		self.sourcesListBox.add(addItemButton)
		
		self.sourceConfigBox.add(Gtk.Label.new("Source Options"))
		self.sourceScroll = Gtk.ScrolledWindow(min_content_height = 100, max_content_height = 100, propagate_natural_height = True, propagate_natural_width = True, overlay_scrolling = False)
		self.sourceConfigBox.add(self.sourcesListBox)
		self.sourceConfigBox.show_all()
		self.sourceConfigPopover.add(self.sourceConfigBox)
		
		self.articlesListToolbar = Gtk.ActionBar()
		self.sourceFavicon = Gtk.Image.new_from_icon_name("action-unavailable-symbolic", Gtk.IconSize.DND)
		self.refreshSourceButton = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.DND)
		self.refreshSourceButton.connect("clicked", lambda x: self.sourceComboBox.emit("changed"))
		self.refreshSourceButton.set_sensitive(False)
		self.subscribeToSourceButton = Gtk.Button.new_from_icon_name("non-starred-symbolic", Gtk.IconSize.DND)
		self.subscribeToSourceButton.set_sensitive(False)
		self.sourceConfigButtonImage = Gtk.Image.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.DND)
		self.sourceConfigButton = Gtk.MenuButton(use_popover = True, popover = self.sourceConfigPopover, direction = Gtk.ArrowType.UP)
		self.sourceConfigButton.get_style_context().add_class("image-button")
		self.sourceConfigButton.add(self.sourceConfigButtonImage)
		self.articlesListToolbar.pack_start(self.refreshSourceButton)
		self.articlesListToolbar.pack_start(Gtk.Separator.new(orientation = Gtk.Orientation.VERTICAL))
		self.articlesListToolbar.pack_start(self.subscribeToSourceButton)
		self.articlesListToolbar.pack_start(self.sourceConfigButton)
		self.articlesListToolbar.pack_end(self.sourceFavicon)
		
		self.articleSubscriptionsBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.articleSubscriptionsLabel = Gtk.Label(label = "Subscriptions")
		self.articleSubscriptionsListBox = Gtk.ListBox()
		self.articleSubscriptionsListBox.set_selection_mode(Gtk.SelectionMode.NONE)
		self.articleSubscriptionsBox.add(self.articleSubscriptionsLabel)
		self.articleSubscriptionsBox.add(self.articleSubscriptionsListBox)
		
		self.articlesListStackSwitcher = Gtk.StackSwitcher(halign = Gtk.Align.END, margin = 4)
		self.articlesListStack = Gtk.Stack()
		self.articlesListStack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
		self.articlesListStack.set_transition_duration(500)
		self.articlesListStackSwitcher.set_stack(self.articlesListStack)
		
		self.articlesListBox = Gtk.Box(orientation = Gtk.Orientation.VERTICAL)
		self.articlesListStore = Gtk.ListStore(str, str)
		self.articlesList = Gtk.TreeView(model = self.articlesListStore)
		self.renderer = Gtk.CellRendererText(ellipsize = Pango.EllipsizeMode.END)
		self.titleColumn = Gtk.TreeViewColumn("Title", self.renderer, text = 0)
		self.titleColumn.props.expand = True
		self.authorColumn = Gtk.TreeViewColumn("Author", self.renderer, text = 1)
		self.authorColumn.props.alignment = 1.0
		self.articlesList.append_column(self.titleColumn)
		self.articlesList.append_column(self.authorColumn)
		self.articlesListFrame = Gtk.ScrolledWindow(propagate_natural_height = True, propagate_natural_width = True, margin = 4, min_content_height = 300, min_content_width = 500, max_content_width = 400, overlay_scrolling = False, vexpand = True, vexpand_set = True)
		self.articlesListFrame.add(self.articlesList)
		self.articlesListOverlay = Gtk.Overlay()
		self.articlesListProgBar = Gtk.ProgressBar(halign = Gtk.Align.CENTER, valign = Gtk.Align.CENTER, show_text = True, text = "Loading sources... (0/8)")
		self.articlesListOverlay.add(self.articlesListFrame)
		self.articlesListOverlay.add_overlay(self.articlesListProgBar)
		self.sourceComboBox = Gtk.ComboBoxText(halign = Gtk.Align.START)
		self.sourceComboBox.set_active(0)
		self.sourceComboBox.connect("changed", self.loadSource)
		for item in sources.get("sources"):
			self.sourceComboBox.append_text(item)
		self.articlesListHeaderBox = Gtk.Box()
		self.articlesListHeaderBox.add(self.sourceComboBox)
		self.articlesListHeaderBox.add(self.articlesListStackSwitcher)
		self.articlesListBox.add(self.articlesListHeaderBox)
		self.articlesListBox.add(self.articlesListStack)
		self.articlesListStack.add_titled(self.articlesListOverlay, "list", "Articles")
		self.articlesListStack.add_titled(self.articleSubscriptionsBox, "sub", "Subscriptions")
		#GLib.timeout_add_seconds(3, self.subscriptionNotify)
		self.articlesListBox.pack_end(self.articlesListToolbar, False, True, 0)
		self.articlesList.connect("row-activated", self.loadArticle)
		self.articlesListSelection = self.articlesList.get_selection()
		self.articlesListBoxExpander = Gtk.Revealer(transition_type = Gtk.RevealerTransitionType.SLIDE_RIGHT, reveal_child = True, transition_duration = 500)
		self.articlesListBoxExpander.add(self.articlesListBox)
		
		self.statusBar = Gtk.Statusbar()
		self.statusBar.push(1, "This is NewsStand " + VERSION + ", made by The Ginger with love.")
		self.toplevelBox.add(self.statusBar)
		
		self.contentBox.pack_start(self.articlesListBoxExpander, False, False, 0)
		self.contentBox.add(Gtk.Separator(orientation = Gtk.Orientation.VERTICAL, margin = 5))
		self.contentBox.pack_start(self.articleBox, True, True, 0)
		GLib.idle_add(self.loadArticleFromQueue)
		GLib.timeout_add(1, self._resize)
		
	def _resize(self):
		self.articleFrame.queue_resize()
		self.articleTextView.queue_resize()
		self.articleImageGallery.queue_resize()
		return True
	
	def loadSource(self, widget):
		self.articlesListStore.clear()
		self.sourceFavicon.set_from_icon_name("content-loading-symbolic", Gtk.IconSize.DND)
		self.refreshSourceButton.set_sensitive(False)
		self._inputStream = None
		SimpleThread(self._loadSource, args=(widget,))
		self.sourceFavicon.set_from_pixbuf(Pixbuf.new_from_stream_at_scale(self._inputStream, 32, -1, True, None))
		self.articles = self.source.articles[:min(500, len(self.source.articles))]
		for item in self.articles:
			if item.title:
				if item.title.strip():
					if len(item.authors):
						self.articlesListStore.append([item.title.lstrip(), item.authors[0]])
					else:
						self.articlesListStore.append([item.title.lstrip(), ""])
		self.refreshSourceButton.set_sensitive(True)
	def _loadSource(self, widget):
		GLib.idle_add(lambda: widget.set_sensitive(False))
		GLib.idle_add(lambda: self.articlesListProgBar.show())
		print(sources.get("sources")[widget.get_active_text()])
		self.source = newspaper.Source(sources.get("sources")[widget.get_active_text()], memoize_articles=False)
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.1))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Downloading source... (1/10)"))
		self.source.download()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.2))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Parsing source... (2/10)"))
		self.source.parse()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.3))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Setting categories... (3/10)"))
		self.source.set_categories()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.4))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Downloading categories... (4/10)"))
		self.source.download_categories()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.5))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Parsing categories... (5/10)"))
		self.source.parse_categories()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.6))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Setting RSS feeds... (6/10)"))
		self.source.set_feeds()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.7))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Downloading RSS metadata... (7/10)"))
		self.source.download_feeds()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.8))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Downloading source favicon... (8/10)"))
		icon = favicon.get(self.source.url)[0].url
		response = urllib.request.urlopen(icon)
		self._inputStream = Gio.MemoryInputStream.new_from_data(response.read(), None)
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(0.9))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Generating articles... (9/10)"))
		self.source.generate_articles()
		GLib.idle_add(lambda: self.articlesListProgBar.set_fraction(1))
		GLib.idle_add(lambda: self.articlesListProgBar.set_text("Generating RSS feed data... (10/10)"))
		url = feedfinder.findfeed(self.source.url)
		if len(url):
			self.articleFeed = feedparser.parse(url[0])
			#print(self.articleFeed.entries[0])
		else:
			self.articleFeed = None
		GLib.idle_add(lambda: self.articlesListProgBar.hide())
		GLib.idle_add(lambda: widget.set_sensitive(True))
	
	def toggleArticleView(self, widget):
		if not self.articlesListBoxExpander.props.reveal_child:
			self.articleListViewToggleButtonImage.set_from_icon_name("go-previous-symbolic", Gtk.IconSize.DND)
		else:
			self.articleListViewToggleButtonImage.set_from_icon_name("go-next-symbolic", Gtk.IconSize.DND)
		self.articlesListBoxExpander.props.reveal_child = not self.articlesListBoxExpander.props.reveal_child
	
	def enableArticlePopover(self):
		self.articlePopoverBox.foreach(lambda item: self._toggleArticlePopover(item, True))
	def disableArticlePopover(self):
		self.articlePopoverBox.foreach(lambda item: self._toggleArticlePopover(item, False))
		self.openItem.set_sensitive(True)
	def _toggleArticlePopover(self, item, sensitive):
		item.set_sensitive(sensitive)
	
	def _handleNotificationClose(self, widget):
		pass
	def subscriptionNotifyReset(self):
		self.articlesListStack.child_set_property(self.articleSubscriptionsBox, "needs-attention", False)
		self.trayIcon.set_status(AppIndicator.IndicatorStatus.ACTIVE)
	def subscriptionNotify(self):
		self.articlesListStack.child_set_property(self.articleSubscriptionsBox, "needs-attention", True)
		self.trayIcon.set_status(AppIndicator.IndicatorStatus.ATTENTION)
		self.subscriptionNotification.props.body = "Source: " + self.newArticles[0]["source"] + " | Title: " + self.newArticles[0]["title"]
		self.subscriptionNotification.show()
		self.subscriptionNotifyChime.play(block = False)
	def loadArticle(self, widget, path, column):
		self.articleSpinner.start()
		self.articleBuffer.set_text("")
		self.articleImages = []
		self.articleImageGallery.foreach(lambda item: item.destroy())
		(model, pathlist) = self.articlesListSelection.get_selected_rows()
		for path in pathlist :
			tree_iter = model.get_iter(path)
			self.articleSelectedName = model.get_value(tree_iter,0)
		selectedArticle = None
		for item in self.articles:
			if item.title:
				if item.title.lstrip().rstrip() == self.articleSelectedName.lstrip().rstrip():
					self.selectedArticle = item
					break
		SimpleThread(self._loadArticle)
		self.articleLabel.set_text(self.articleSelectedName.lstrip().rstrip())
		self.articleBuffer.set_text("\n\n" + self.selectedArticle.text + "\n\n")
		self.articleBuffer.insert_pixbuf(self.articleBuffer.get_start_iter(), self.topImage)
		self._formatArticle()
	def _formatArticle(self):
		galleryStart = self.articleBuffer.get_end_iter()
		galleryStart.backward_char()
		imageEnd = self.articleBuffer.get_start_iter()
		imageEnd.forward_char()
		self.articleBuffer.apply_tag(self.centerTag, self.articleBuffer.get_start_iter(), imageEnd)
		self.articleBuffer.apply_tag(self.centerTag, galleryStart, self.articleBuffer.get_end_iter())
		self.articleBuffer.apply_tag(self.fontSizeTag, self.articleBuffer.get_start_iter(), self.articleBuffer.get_end_iter())
		for item in self.articleImages:
			if self.articleImages.index(item) != 0:
				i = Gtk.Image.new_from_pixbuf(item)
				i.props.expand = False
				self.articleImageGallery.add(i)
		self.articleImageGallery.show_all()
		self.enableArticlePopover()
		self.articleSpinner.stop()
	def _loadArticle(self):
		self.selectedArticle.download()
		self.selectedArticle.parse()
		print(self.selectedArticle.images)
		for item in self.selectedArticle.images:
			response = urllib.request.urlopen(item)
			inputStream = Gio.MemoryInputStream.new_from_data(response.read(), None)
			if self.selectedArticle.top_image == item:
				self.topImage = Pixbuf.new_from_stream_at_scale(inputStream, 500, -1, True, None)
			else:
				self.articleImages.append(Pixbuf.new_from_stream_at_scale(inputStream, 250, -1, True, None))
	
	def saveArticle(self, widget):
		fileChooser = Gtk.FileChooserDialog(action = Gtk.FileChooserAction.SAVE, icon_name = "document-save", do_overwrite_confirmation = True, buttons = ("Nevermind.", Gtk.ResponseType.CANCEL, "Save!", Gtk.ResponseType.ACCEPT))
		fileChooser.add_choice("filetype", "Filetype: ", ["txt", "nsaf"], ["Text File", "NewsStand Article File"])
		fileChooser.set_current_folder("~/Documents/Articles")
		results = fileChooser.run()
		fileChooser.hide()
		if results == Gtk.ResponseType.ACCEPT:
			if fileChooser.get_choice("filetype") == "nsaf":
				imageDataList = []
				for item in self.articleImages:
					imageDataList.append(item.save_to_bufferv("jpeg", [], []))
				pickle.dump({"title": self.selectedArticle.title, "content": self.selectedArticle.text, "images": imageDataList}, open(fileChooser.get_filename() + ".nsaf", "wb"))
	def loadArticleFromFile(self, widget, filename = None):
		self.articleBuffer.set_text("")
		self.articleImageGallery.foreach(lambda item: item.destroy())
		self.articleImages = []
		results = None
		if filename == None:
			fileOpenFilter = Gtk.FileFilter()
			fileOpenFilter.add_pattern("*.nsaf")
			fileChooser = Gtk.FileChooserDialog(action = Gtk.FileChooserAction.OPEN, icon_name = "document-open", buttons = ("Nevermind.", Gtk.ResponseType.CANCEL, "Open!", Gtk.ResponseType.ACCEPT))
			fileChooser.set_filter(fileOpenFilter)
			results = fileChooser.run()
			fileChooser.hide()
		if results == Gtk.ResponseType.ACCEPT or filename != None:
			if filename != None:
				loadedArticle = pickle.load(open(filename, "rb"))
			else:
				loadedArticle = pickle.load(open(fileChooser.get_filename(), "rb"))
			self.articleLabel.set_text(loadedArticle["title"])
			self.articleBuffer.set_text("\n\n" + loadedArticle["content"])
			#print(bytes(loadedArticle["image"]["data"][1].hex(), "utf-8"))
			PBLoader = GdkPixbuf.PixbufLoader()
			PBLoader.write(loadedArticle["images"][0][1])
			PBLoader.close()
			self.articleBuffer.insert_pixbuf(self.articleBuffer.get_start_iter(), PBLoader.get_pixbuf())
			for item in loadedArticle["images"]:
				PBLoader = GdkPixbuf.PixbufLoader()
				PBLoader.write(item[1])
				PBLoader.close()
				self.articleImages.append(PBLoader.get_pixbuf())
			self._formatArticle()
	
	def resetFontSize(self, widget):
		self.fontSizeTag.props.scale = 1.0
	def increaseFontSize(self, widget):
		if self.fontSizeTag.props.scale < 2.0:
			self.fontSizeTag.props.scale += 0.1
	def decreaseFontSize(self, widget):
		if self.fontSizeTag.props.scale > 0.6:
			self.fontSizeTag.props.scale -= 0.1
	
	def toggleFullscreen(self, widget):
		if widget.get_active():
			widget.get_child().set_from_icon_name("view-restore-symbolic", Gtk.IconSize.DND)
			self.fullscreen()
		else:
			widget.get_child().set_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.DND)
			self.unfullscreen()
	
	def shareToLK(self):
		self.showLoadingBanner("Sharing to LinkedIn...")
		self.selectedArticle.nlp()
		webbrowser.open("https://www.linkedin.com/shareArticle?mini=true&url=" + self.selectedArticle.url + "&title=Look%20at%20this%20news%20article!%20%22" + self.selectedArticle.title + "%22&summary=I%20found%20this%20cool%20news%20article%20online!%20Here's%20a%20summary%3A%0A" + self.selectedArticle.summary)
		self.hideLoadingBanner()
	def shareToTW(self):
		self.showLoadingBanner("Sharing to Twitter...")
		self.selectedArticle.nlp()
		webbrowser.open("https://twitter.com/intent/tweet?text=Hey,%20check%20out%20this%20news%20article%20I%20found!%20" + self.selectedArticle.url + "%20%23" + self.source.brand + "%20%20%23" + self.selectedArticle.keywords[0] + "%20%23" + self.selectedArticle.keywords[0] + "%20%23" + self.selectedArticle.keywords[0] + "%20%23NewsStand%20Powered%20by%20NewsStand%20" + "https://github.com/GingerIndustries/newsstand")
		self.hideLoadingBanner()
	def shareToPintrest(self):
		self.showLoadingBanner("Sharing to Pintrest...")
		self.selectedArticle.nlp()
		webbrowser.open("https://pinterest.com/pin/create/button/?url=" + self.selectedArticle.url + "&media=" + self.selectedArticle.top_image + "&description=Hey,%20look%20at%20this%20cool%20article%20I%20found!%0AHere's%20a%20summary%3A%0A" + self.selectedArticle.summary + "%0AYou%20can%20click%20the%20image%20to%20open%20it!%0A%0APowered%20by%20NewsStand%20" + "https://github.com/GingerIndustries/newsstand")
		self.hideLoadingBanner()
	def shareToEmail(self, widget):
		dialog = Gtk.Dialog(use_header_bar = True)
		dialog.set_skip_taskbar_hint(True)
		okButton = dialog.add_button("OK", Gtk.ResponseType.OK)
		okButton.get_style_context().add_class("suggested-action")
		okButton.connect("clicked", self._shareToEmailHandler)
		okButton.set_sensitive(False)
		closeButton = dialog.add_button("Nevermind!", Gtk.ResponseType.CANCEL)
		closeButton.connect("clicked", dialog.hide)
		contentArea = dialog.get_content_area()
		label = Gtk.Label(label="Who shall recieve this message?")
		labelBox = Gtk.Box()
		helpPopover = Gtk.Popover(position = Gtk.PositionType.BOTTOM, constrain_to = Gtk.PopoverConstraint.NONE)
		helpLabel = Gtk.Label(label="<span size = \"small\">Emails must be separated by commas, but no spaces.\nExample: email@email.io,email2@email.io</span>", use_markup = True)
		helpPopover.add(helpLabel)
		helpLabel.show()
		helpButton = Gtk.MenuButton(use_popover = True, popover = helpPopover)
		helpButton.add(Gtk.Image.new_from_icon_name("dialog-question-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
		helpButton.get_style_context().add_class("image-button")
		helpButton.get_style_context().add_class("flat")
		helpButton.get_style_context().add_class("circular")
		labelBox.add(label)
		labelBox.add(helpButton)
		entry = Gtk.Entry(input_purpose = Gtk.InputPurpose.EMAIL)
		def _checkEntry(widget):
			widget.get_style_context().remove_class("error")
			if len(widget.get_text()):
				okButton.set_sensitive(True)
			else:
				okButton.set_sensitive(False)
		entry.connect("changed", _checkEntry)
		contentArea.add(labelBox)
		contentArea.add(entry)
		dialog.show_all()
		dialog.run()
	def _shareToEmailHandler(self, widget):
		entry = widget.get_parent().get_parent().get_content_area().get_children()[1]
		if not " " in entry.get_text():
			widget.get_parent().get_parent().hide()
			def _run():
				self.showLoadingBanner("Sending as an email...")
				self.selectedArticle.nlp()
				openutils.mailto(address = entry.get_text(), to = entry.get_text(), subject = "Look at this cool news article!", body = "!Hey, check out this cool news article I found! " + self.selectedArticle.url + "\nHere's a summary:\n" + self.selectedArticle.summary + "\n\nPowered by NewsStand: " + "https://github.com/GingerIndustries/newsstand")
				self.hideLoadingBanner()
			SimpleThread(_run)
		else:
			entry.get_style_context().add_class("error")
	def hideLoadingBanner(self):
		self.loadingInfoBar.set_revealed(False)
		GLib.timeout_add(150, self.loadingInfoBar.hide)
	def showLoadingBanner(self, text="Loading..."):
		self.loadingInfoBarLabel.set_text(text)
		self.loadingInfoBar.show()
		self.loadingInfoBar.set_revealed(True)
	
	def showArticleDetails(self, widget):
		detailsDialog = Gtk.Dialog(use_header_bar = True, title = "Article info")
		detailsString = ""
		detailsString += "Article title: " + self.selectedArticle.title
		if len(self.selectedArticle.authors) == 1:
			detailsString += "\nAuthor: " + self.selectedArticle.authors[0]
		else:
			detailsString += "\nAuthors: "
			for item in self.selectedArticle.authors:
				detailsString += item
				if item != self.selectedArticle.authors[-1]:
					detailsString += ", "
				if item == self.selectedArticle.authors[-2]:
					detailsString += "and "
		detailsString += "\nArticle date: "
		if self.selectedArticle.publish_date:
			detailsString += self.selectedArticle.publish_date.strftime("%A, %b %d %Y %I:%M %p")
		
		detailsLabel = Gtk.Label(label = detailsString, wrap = True, wrap_mode = Pango.WrapMode.WORD)
		detailsDialog.get_content_area().add(detailsLabel)
		detailsDialog.show_all()
		detailsDialog.run()
	
	def _getSourceFromWidget(self, widget):
		_sources = sources.get("sources")
		return (list(_sources.keys())[list(_sources.values()).index(_sources[widget.get_parent().get_parent().get_parent().label.get_text()])], _sources[widget.get_parent().get_parent().get_parent().label.get_text()]) #python at its finest lmao
	def editSource(self, widget):
		source = self._getSourceFromWidget(widget)
		dialog = Gtk.Dialog(use_header_bar = True)
		dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
		okButton = dialog.add_button("Apply & Restart", Gtk.ResponseType.OK)
		okButton.get_style_context().add_class("suggested-action")
		contentArea = dialog.get_content_area()
		nameEntry = Gtk.Entry(text = source[0], max_length = 25, margin_bottom = 10, margin_end = 50)
		urlEntry = Gtk.Entry(text = source[1].split("http://",1)[1], input_purpose = Gtk.InputPurpose.URL, margin_end = 50)
		contentArea.add(nameEntry)
		contentArea.add(urlEntry)
		dialog.show_all()
		results = dialog.run()
		dialog.hide()
		if results == Gtk.ResponseType.OK:
			def _update():
				oldSources = dict(sources.get("sources"))
				oldSources[nameEntry.get_text()] = oldSources.pop(source[0])
				oldSources.update({nameEntry.get_text(): "http://" + urlEntry.get_text()})
				sources.setsave("sources", oldSources)
			self._restart(_update)
	
	def _restart(self, callbackFunc, text = "Success!"):
		dialog = Gtk.MessageDialog(text = text, secondary_text = "Saving data and restarting NewsStand...")
		dialog.show()
		callbackFunc()
		SimpleThread(lambda: sleep(1)) #This is so that the user doesn't panic because NewsStand restarted randomly
		dialog.hide()
		s.close()
		_gpidfile.__exit__()
		os.execl(sys.executable, sys.executable, *sys.argv)
	
	def deleteSource(self, widget):
		source = self._getSourceFromWidget(widget)
		dialog = Gtk.Dialog(use_header_bar = True)
		dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
		okButton = dialog.add_button("Delete & Restart", Gtk.ResponseType.OK)
		okButton.get_style_context().add_class("destructive-action")
		contentArea = dialog.get_content_area()
		deleteLabel = Gtk.Label(label = "Delete source: " + source[0] + "?")
		mordorLabel = Gtk.Label(label = "<span fgcolor = \"#FF0000\" font_weight = \"bold\">Caution: One does not simply restore a deleted source.</span>", use_markup = True)
		contentArea.add(deleteLabel)
		contentArea.add(mordorLabel)
		dialog.show_all()
		results = dialog.run()
		if results == Gtk.ResponseType.OK:
			dialog.hide()
			def _update():
				sourcesList = sources.get("sources")
				sourcesList.pop(source[0])
				sources.setsave("sources", sourcesList)
			self._restart(_update, "Deleted.")
		else:
			dialog.hide()
	def addSource(self, widget):
		self.status = []
		dialog = Gtk.Dialog(use_header_bar = True)
		dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
		okButton = dialog.add_button("Apply & Restart", Gtk.ResponseType.OK)
		okButton.get_style_context().add_class("suggested-action")
		contentArea = dialog.get_content_area()
		nameEntry = Gtk.Entry(placeholder_text = "Name", max_length = 25, margin_bottom = 10, margin_end = 50)
		urlEntry = Gtk.Entry(placeholder_text = "URL", input_purpose = Gtk.InputPurpose.URL, margin_end = 50)
		contentArea.add(nameEntry)
		contentArea.add(urlEntry)
		dialog.show_all()
		okButton.grab_focus()
		results = dialog.run()
		dialog.hide()
		if results == Gtk.ResponseType.OK:
			loaderDialog = Gtk.Dialog(modal = True)
			spinner = Gtk.Spinner()
			spinner.set_size_request(64, 64)
			spinner.start()
			label = Gtk.Label(label = "Connecting to source: " + nameEntry.get_text() + "\nPlease wait up to 5 seconds...")
			content = loaderDialog.get_content_area()
			content.add(label)
			content.add(spinner)
			content.show_all()
			loaderDialog.show()
			SimpleThread(self._addSource, args=(urlEntry, nameEntry,))
			print(self.status)
			if self.status[0] == "err":
				loaderDialog.hide()
				if self.status[1] == "httperr":
					self.infoBarLabel.set_text("Unable to add source '" + nameEntry.get_text() + "'!\n[Invalid URL: " + self.status[2] + "]")
					self.infoBar.show()
					self.infoBar.set_revealed(True)
				elif self.status[1] == "notfound":
					self.infoBarLabel.set_text("Unable to add source '" + nameEntry.get_text() + "'!\n[Server not found]")
					self.infoBar.show()
					self.infoBar.set_revealed(True)
				elif self.status[1] == "timeout":
					self.infoBarLabel.set_text("Unable to add source '" + nameEntry.get_text() + "'!\n[Request timed out]")
					self.infoBar.show()
					self.infoBar.set_revealed(True)
			else:
				loaderDialog.hide()
				def _update():
					sourcesList = sources.get("sources")
					sourcesList[nameEntry.get_text()] = "http://" + urlEntry.get_text()
					sources.setsave("sources", sourcesList)
				self._restart(_update)
		else:
			dialog.hide()
				
	def _addSource(self, urlEntry, nameEntry):
		h = httplib2.Http(timeout = 5)
		try:
			resp = h.request("http://" + urlEntry.get_text(), "HEAD")
			print(resp)
			if not int(resp[0]['status']) < 400:
				self.status = ["err", "httperr", resp[0]['status']]
			elif "connection" in resp[0]:
				if resp[0]["connection"] == "close":
					self.status = ["err", "notfound"]
		except httplib2.error.ServerNotFoundError:
			self.status = ["err", "notfound"]
		except socket.timeout:
			self.status = ["err", "timeout"]
		else:
			if self.status == []:
				self.status = ["ok"]
	def show(self):
		self.set_position(Gtk.WindowPosition.CENTER)
		self.show_all()
		self.articlesListProgBar.hide()
		self.infoBar.hide()
		self.loadingInfoBar.hide()
	def exit(self, widget):
		exitDialog = Gtk.MessageDialog(icon_name = "process-stop-symbolic", buttons = Gtk.ButtonsType.YES_NO, message_type = Gtk.MessageType.QUESTION, text = "Exit NewsStand", secondary_text = "Are you sure that you want\n to exit NewsStand?")
		result = exitDialog.run()
		exitDialog.hide()
		if result == Gtk.ResponseType.YES:
			Gtk.main_quit()
	
	def loadArticleFromQueue(self):
		global fileLoadQueue
		if fileLoadQueue != b"":
			self.show()
			self.present()
			if fileLoadQueue != "nofile":
				self.loadArticleFromFile(widget = None, filename = fileLoadQueue)
			fileLoadQueue = b""
		return True
		
def _listen():
	global fileLoadQueue
	s.listen()
	while True:
		conn, addr = s.accept()
		filedat = conn.recv(1024)
		if filedat.decode() == "exit":
			Gtk.main_quit()
		else:
			fileLoadQueue = filedat.decode()
def startServSocket():
	s.bind(("127.0.0.1", 13254))
	servListenThread = threading.Thread(target = _listen, daemon = True)
	servListenThread.start()
try:
	with pidfile.PIDFile() as _pidfile:
		_gpidfile = _pidfile
		args = parser.parse_args()
		win = Window()
		win.show()
		if args.exit:
			print("NewsStand is not already running, so --exit is invalid. Starting NewsStand anyway...")
		if args.file != "__nofile__":
			fileLoadQueue = args.file
		startServSocket()
		Gtk.main()
except pidfile.AlreadyRunningError:
	args = parser.parse_args()
	print("already running")
	s.connect(("127.0.0.1", 13254))
	if args.file != "__nofile__":
		s.send(bytes(args.file, "utf-8"))
	elif not args.exit:
		s.send(b"nofile")
	else:
		s.send(b"exit")
	s.close()
	sys.exit(0)

