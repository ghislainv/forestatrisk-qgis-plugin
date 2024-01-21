# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ForestatriskPlugin
                                 A QGIS plugin
 Deforestation risk mapping.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-12-13
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Ghislain Vieilledent (Cirad)
        email                : ghislain.vieilledent@cirad.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import subprocess
import platform

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .forestatrisk_plugin_dialog import ForestatriskPluginDialog

# Local forestatrisk functions
from .far_functions import far_get_variables, far_sample_obs


class ForestatriskPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # Initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            "i18n",
            f"ForestatriskPlugin_{locale}.qm")

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&Forestatrisk Plugin")
        self.args = None  # GV: arguments for far functions.

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.dlg = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("ForestatriskPlugin", message)

    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ":/plugins/foo/bar.png") or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ":/plugins/forestatrisk_plugin/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("Modelling and forecasting deforestation "
                         "in the tropics"),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr("&Forestatrisk Plugin"),
                action)
            self.iface.removeToolBarIcon(action)

    def set_exe_path(self):
        """Add folder with windows executables to PATH."""
        is_win = platform.system() == "Windows"
        is_64bit = "PROGRAMFILES(X86)" in list(os.environ.keys())
        if is_win and is_64bit:
            os.environ["PATH"] += os.pathsep + os.path.join(self.plugin_dir,
                                                            "winexe")
            # Rclone info
            cmd = ["rclone", "--version"]
            result = subprocess.run(cmd, capture_output=True, check=True)
            result = result.stdout.splitlines()
            print(result[0].decode())

            # osmconvert info
            cmd = ["osmconvert", "--help"]
            result = subprocess.run(cmd, capture_output=True, check=True)
            result = result.stdout.splitlines()
            print(result[1].decode())

            # osmfilter info
            cmd = ["osmfilter", "--help"]
            result = subprocess.run(cmd, capture_output=True, check=True)
            result = result.stdout.splitlines()
            print(result[1].decode())

    def catch_arguments(self):
        """Catch arguments from ui"""
        # Get variables
        workdir = self.dlg.workdir.text()
        iso = self.dlg.isocode.text()
        proj = self.dlg.proj.text()
        fcc_source = self.dlg.fcc_source.text()
        perc = self.dlg.perc.text()
        remote_rclone = self.dlg.remote_rclone.text()
        gdrive_folder = self.dlg.gdrive_folder.text()
        wdpa_key = self.dlg.wdpa_key.text()
        # Sampling observations
        nsamp = self.dlg.nsamp.text()
        adapt = self.dlg.adapt.isChecked()
        seed = self.dlg.seed.text()
        csize = self.dlg.csize.text()
        # Default values
        iso = "MTQ" if iso == "" else iso
        if workdir == "":
            if platform.system() == "Windows":
                workdir = os.path.join(os.environ["HOMEDRIVE"],
                                       os.environ["HOMEPATH"],
                                       "far-qgis", iso)
            else:
                workdir = os.path.join(os.environ["HOME"],
                                       "far-qgis", iso)
        proj = "EPSG:5490" if proj == "" else proj
        fcc_source = "jrc" if fcc_source == "" else fcc_source
        perc = "50" if perc == "" else perc
        remote_rclone = "gdrive_gv" if remote_rclone == "" else remote_rclone
        if gdrive_folder == "":
            gdrive_folder = "GEE/GEE-far-qgis-plugin"
        # No default value for wdpa_key, this is handled in far_get_variables
        nsamp = 10000 if nsamp == "" else nsamp
        seed = 1234 if seed == "" else seed
        csize = 10 if csize == "" else csize
        # Dictionary of arguments for far functions
        self.args = {
            "workdir": workdir, "isocode": iso, "proj": proj,
            "fcc_source": fcc_source, "perc": perc,
            "remote_rclone": remote_rclone, "gdrive_folder": gdrive_folder,
            "wdpa_key": wdpa_key,
            "nsamp": nsamp, "adapt": adapt, "seed": seed,
            "csize": csize}

    def get_variables(self):
        """Get variables"""
        self.catch_arguments()
        far_get_variables(iface=self.iface,
                          workdir=self.args["workdir"],
                          isocode=self.args["isocode"],
                          proj=self.args["proj"],
                          fcc_source=self.args["fcc_source"],
                          perc=self.args["perc"],
                          remote_rclone=self.args["remote_rclone"],
                          gdrive_folder=self.args["gdrive_folder"],
                          wdpa_key="wdpa_key")

    def sample_obs(self):
        """Sample observations"""
        self.catch_arguments()
        far_sample_obs(iface=self.iface,
                       workdir=self.args["workdir"],
                       proj=self.args["proj"],
                       nsamp=self.args["nsamp"],
                       adapt=self.args["adapt"],
                       seed=self.args["seed"],
                       csize=self.args["csize"])

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation)
        # and keep reference.
        # Only create GUI ONCE in callback, so that it will only
        # load when the plugin is started
        if self.first_start is True:
            self.first_start = False
            self.dlg = ForestatriskPluginDialog()
            # Set executable path
            self.set_exe_path()

        # Call to functions if buttons ares clicked
        self.dlg.run_var.clicked.connect(self.get_variables)
        self.dlg.run_samp.clicked.connect(self.sample_obs)

        # show the dialog
        self.dlg.show()
        result = self.dlg.exec_()
        if result:
            pass

# End of file
