## import hotshot
## _prof = hotshot.Profile("hotshot.prf")

import os, sys, traceback, sets, string, re

import wx
import wx.xrc as xrc

from wxHelper import GUI_ID
from MiscEvent import MiscEventSourceMixin, ResendingMiscEvent

from WikiExceptions import *

import Configuration



class MainAreaPanel(wx.Notebook, MiscEventSourceMixin):
    """
    The main area panel is embedded in the PersonalWikiFrame and holds and
    controls the doc page presenters.
    """

    def __init__(self, parent, mainControl, id=-1):
        wx.Notebook.__init__(self, parent, id)
        MiscEventSourceMixin.__init__(self)

        self.mainControl = mainControl
        self.mainControl.getMiscEvent().addListener(self)

        self.currentDocPagePresenter = None
        self.docPagePresenters = []
#         self.currentDocPagePresenterRMEvent = ResendingMiscEvent(self)

        res = xrc.XmlResource.Get()
        self.contextMenu = res.LoadMenu("MenuDocPagePresenterTabPopup")


        # Last presenter for which a context menu was shown
        self.lastContextMenuPresenter = None

        self.ignorePageChangedEvent = False

        wx.EVT_NOTEBOOK_PAGE_CHANGED(self, self.GetId(),
                self.OnNotebookPageChanged)
        wx.EVT_CONTEXT_MENU(self, self.OnContextMenu)
        wx.EVT_SET_FOCUS(self, self.OnFocused)
#         EVT_AFTER_FOCUS(self, self.OnAfterFocus)

        wx.EVT_MENU(self, GUI_ID.CMD_CLOSE_THIS_TAB, self.OnCloseThisTab)
        wx.EVT_MENU(self, GUI_ID.CMD_CLOSE_CURRENT_TAB, self.OnCloseCurrentTab)
        wx.EVT_MENU(self, GUI_ID.CMD_THIS_TAB_SHOW_SWITCH_EDITOR_PREVIEW,
                self.OnCmdSwitchThisEditorPreview)


    def close(self):
        for p in self.docPagePresenters:
            p.close()


    def getCurrentDocPagePresenter(self):
        return self.currentDocPagePresenter
        
    def getCurrentTabTitle(self):
        sel = self.GetSelection()
        if sel == -1:
            return u""
        
        return self.GetPageText(sel)


    def getDocPagePresenters(self):
        return self.docPagePresenters

    def getIndexForDocPagePresenter(self, presenter):
        for i, p in enumerate(self.docPagePresenters):
            if p is presenter:
                return i
        
        return -1


    # TODO What about WikidPadHooks?
    def setCurrentDocPagePresenter(self, currentPresenter):
        """
        Mainly called by OnNotebookPageChanged to inform presenters
        about change
        """
        if not (self.currentDocPagePresenter is currentPresenter):
            self.currentDocPagePresenter = currentPresenter
            for p in self.docPagePresenters:
                p.setVisible(p is currentPresenter)
            rMEvent = self.mainControl.getCurrentDocPagePresenterRMEvent()
            rMEvent.setWatchedEvents((self.currentDocPagePresenter.getMiscEvent(),))
            self.mainControl.refreshPageStatus()
            self.fireMiscEventKeys(("changed current docpage presenter",))


    def showDocPagePresenter(self, currentPresenter):
        """
        Sets current presenter by changing the active tab in the
        main area notebook which in turn calls setCurrentDocPagePresenter()
        """
        i = self.getIndexForDocPagePresenter(currentPresenter)
        if i > -1:
            self.SetSelection(i)


#     def getCurrentDocPagePresenterRMEvent(self):
#         """
#         This ResendingMiscEvent resends any messsages from the currently
#         active DocPagePresenter
#         """
#         return self.currentDocPagePresenterRMEvent


    def appendDocPagePresenterTab(self, presenter):
        self.docPagePresenters.append(presenter)
        self.AddPage(presenter, "    ")
        presenter.getMiscEvent().addListener(self)

        presenter.switchSubControl("textedit")

        if Configuration.isLinux():
            presenter.Show(True)

        if self.getCurrentDocPagePresenter() is None:
            self.setCurrentDocPagePresenter(presenter)
            
        return presenter


    def closeDocPagePresenterTab(self, presenter):
        if len(self.docPagePresenters) < 2:
            # At least one tab must stay
            return

        idx = self.getIndexForDocPagePresenter(presenter)
        if idx == -1:
            return
            
        # Prepare presenter for closing
        presenter.close()
        
        # Actual deletion
        del self.docPagePresenters[idx]
        self.DeletePage(idx)


    def closeAllButCurrentTab(self):
        """
        Close all tabs except the current one.
        """
        current = self.currentDocPagePresenter
        
        # Loop over copy of the presenter list
        for presenter in self.docPagePresenters[:]:
            if len(self.docPagePresenters) < 2:
                # At least one tab must stay
                return
            
            if presenter is current:
                continue
            
            self.closeDocPagePresenterTab(presenter)


    def switchDocPagePresenterTabEditorPreview(self, presenter):
        """
        Switch between editor and preview in the given presenter
        (if presenter is owned by the MainAreaPanel).
        """
        if not presenter in self.docPagePresenters:
            return
        
        scName = presenter.getCurrentSubControlName()
        if scName != "textedit":
            presenter.switchSubControl("textedit", gainFocus=True)
        else:
            presenter.switchSubControl("preview", gainFocus=True)


    def OnNotebookPageChanged(self, evt):
        # Tricky hack to set focus to the notebook page
        if self.ignorePageChangedEvent:
            evt.Skip()
            self.ignorePageChangedEvent = False
            return

        try:
            presenter = self.docPagePresenters[evt.GetSelection()]
            self.setCurrentDocPagePresenter(presenter)

            # Flag the event to ignore and resend it
            # it is then processed by wx.Notebook code
            # where the focus is set to the notebook itself
            self.ignorePageChangedEvent = True
            self.ProcessEvent(evt)

            # Now we can set the focus to the presenter
            # which in turn sets it to the active subcontrol
            presenter.SetFocus()
#             self.GetPage(evt.GetSelection()).SetFocus()
        except (IOError, OSError, DbAccessError), e:
            self.mainControl.lostAccess(e)
            raise #???
        
        # evt.Skip()


    def OnContextMenu(self, evt):
        pos = self.ScreenToClient(wx.GetMousePosition())
        tab = self.HitTest(pos)[0]
        if tab == wx.NOT_FOUND:
            return
        
        self.lastContextMenuPresenter = self.docPagePresenters[tab]
        # Show menu
        self.PopupMenu(self.contextMenu)



    def OnFocused(self, evt):
        p = self.GetCurrentPage()
        if p is not None:
            p.SetFocus()


    def OnCloseThisTab(self, evt):
        if self.lastContextMenuPresenter is not None:
            self.closeDocPagePresenterTab(self.lastContextMenuPresenter)

    def OnCloseCurrentTab(self, evt):
        self.closeDocPagePresenterTab(self.getCurrentDocPagePresenter())


    def OnCmdSwitchThisEditorPreview(self, evt):
        """
        Switch between editor and preview in the presenter for which
        context menu was used.
        """
        if self.lastContextMenuPresenter is not None:
            self.switchDocPagePresenterTabEditorPreview(self.lastContextMenuPresenter)



    def miscEventHappened(self, miscevt):
        if miscevt.getSource() in self.docPagePresenters:
            if miscevt.has_key("changed presenter title"):
                presenter = miscevt.getSource()
                idx = self.getIndexForDocPagePresenter(presenter)
                if idx > -1:
                    self.SetPageText(idx,
                            presenter.getLongTitle())
                            
#                     # TODO (Re)move this
# #                     if presenter is self.getCurrentDocPagePresenter():
#                     title = (u"Wiki: %s - %s" %
#                             (self.mainControl.getWikiConfigPath(),
#                             presenter.getShortTitle()))
# #                     if self.mainControl.GetTitle() != title:
#                     self.mainControl.SetTitle(title)

                    if presenter is self.getCurrentDocPagePresenter():
                        self.mainControl.refreshPageStatus()

        elif miscevt.getSource() is self.mainControl:
            if miscevt.has_key("closed current wiki"):
                self.closeAllButCurrentTab()



