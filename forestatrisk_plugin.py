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
import sys

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

# Import the forestatrisk package
try:
    import forestatrisk as far
except ImportError:
    plugin_dir = os.path.dirname(os.path.realpath(__file__))
    far_dir = os.path.join(plugin_dir, "forestatrisk")
    sys.path.append(far_dir)
    import forestatrisk as far

import ee
from matplotlib import pyplot as plt
import pandas as pd
from pywdpa import get_token

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .forestatrisk_plugin_dialog import ForestatriskPluginDialog

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
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
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

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

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
            text=self.tr("Mapping deforestation risk"),
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

    # ======================================================
    # Additional functions here between unload() and run()
    # ======================================================

    def run_forestatrisk(self):
        """Run forestatrisk."""

        # QGis plugin arguments
        ISO3 = "MTQ"
        PROJ = "EPSG:5490"
        WORK_DIR = "/home/ghislain/Bureau/tests"
        FCC_SOURCE = "jrc"
        PERC = 50
        GDRIVE_REMOTE_RCLONE = "gdrive_gv"
        GDRIVE_FOLDER = "GEE/GEE-forestatrisk-notebooks"

        # Output directories
        DATA_RAW_DIR = "data_raw"
        DATA_DIR = "data"
        OUTPUT_DIR = "outputs"
        far.make_dir(DATA_RAW_DIR)
        far.make_dir(DATA_DIR)
        far.make_dir(OUTPUT_DIR)

        # Print far doc and version
        print(far.__doc__)
        print(f"version: {far.__version__}")

        # Initialize Earth Engine
        ee.Initialize()

        # Set WDPA API key
        with open(os.path.join(WORK_DIR, ".env")) as f:
            [name_key, value_key] = f.read().split("=")
            os.environ["WDPA_KEY"] = value_key.replace("\"", "")

        # Set working directory
        os.chdir(WORK_DIR)

        # Compute gee forest data
        far.data.country_forest_run(
            iso3=ISO3,
            proj="EPSG:4326",
            output_dir=DATA_RAW_DIR,
            keep_dir=True,
            fcc_source=FCC_SOURCE,
            perc=PERC,
            gdrive_remote_rclone=GDRIVE_REMOTE_RCLONE,
            gdrive_folder=GDRIVE_FOLDER)

        # Download data
        far.data.country_download(
            iso3=ISO3,
            gdrive_remote_rclone=GDRIVE_REMOTE_RCLONE,
            gdrive_folder=GDRIVE_FOLDER,
            output_dir=DATA_RAW_DIR)

        # Compute explanatory variables
        far.data.country_compute(
            iso3=ISO3,
            temp_dir=DATA_RAW_DIR,
            output_dir=DATA_DIR,
            proj=PROJ,
            data_country=True,
            data_forest=True,
            keep_temp_dir=True)

        # Plot
        ifile = os.path.join(DATA_DIR, "forest/fcc123.tif")
        ofile = os.path.join(OUTPUT_DIR, "fcc123.png")
        bfile = os.path.join(DATA_DIR, "ctry_PROJ.shp")
        fig_fcc123 = far.plot.fcc123(
            input_fcc_raster=ifile,
            maxpixels=1e8,
            output_file=ofile,
            borders=bfile,
            linewidth=0.3,
            figsize=(6, 5), dpi=500)
        plt.close(fig_fcc123)

    # ======================================================
    # End of additional functions
    # ======================================================

    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start is True:
            self.first_start = False
            self.dlg = ForestatriskPluginDialog()

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            self.run_forestatrisk()
            # pass

# End of file
