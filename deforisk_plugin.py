# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DeforiskPlugin
                                 A QGIS plugin
 Deforestation risk mapping.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-12-13
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Ghislain Vieilledent (Cirad)
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

# Define double undescore variables
# https://peps.python.org/pep-0008/#module-level-dunder-names
__author__ = "Ghislain Vieilledent and Thomas Arsouze"
__email__ = "ghislain.vieilledent@cirad.fr, thomas.arsouze@cirad.fr"
__version__ = "0.2dev"

import os
import subprocess
import platform
import random

from qgis.core import Qgis, QgsApplication

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

import pandas as pd
import forestatrisk as far
import riskmapjnr as rmj

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .deforisk_plugin_dialog import DeforiskPluginDialog

# Local far functions
from .far_functions import (
    FarGetVariablesTask,
    FarSampleObsTask,
    FarCalibrateTask,
    FarPredictTask,
)

# Local rmj function
from .rmj_functions import (
    RmjCalibrateTask,
    RmjPredictTask,
)

# Local val function
from .val_functions import (
    EmptyTask,
    ValidateTask
)


class DeforiskPlugin:
    """QGIS Plugin Implementation."""

    OUT = "outputs"
    PERIODS = ["calibration", "validation"]
    FAR_MODELS = ["icar", "glm", "rf"]

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
            f"DeforiskPlugin_{locale}.qm")

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&Deforisk")
        self.args = None  # GV: arguments for far functions.

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        self.dlg = None

        # Task manager
        self.tm = QgsApplication.taskManager()

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
        return QCoreApplication.translate("DeforiskPlugin", message)

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

        icon_path = ":/plugins/deforisk-qgis-plugin/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("Create and compare maps of deforestation risk "
                         "in the tropics"),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr("&Deforisk"),
                action)
            self.iface.removeToolBarIcon(action)

    def print_dependency_version(self):
        """Print package versions."""
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
        # forestatrisk
        print(f"forestatrisk v{far.__version__}")
        # riskmapjnr
        print(f"riskmapjnr v{rmj.__version__}")

    def set_exe_path(self):
        """Add folder with windows executables to PATH."""
        is_win = platform.system() == "Windows"
        is_64bit = "PROGRAMFILES(X86)" in list(os.environ.keys())
        if is_win and is_64bit:
            os.environ["PATH"] += os.pathsep + os.path.join(
                self.plugin_dir,
                "winexe"
            )
        self.print_dependency_version()

    def task_description(self, task_name, model=None, date=None,
                         csize_val=None):
        """Write down task description."""
        isocode = self.args["isocode"]
        get_fcc_args = self.args["get_fcc_args"]
        years = get_fcc_args["years"]
        years = years.replace(" ", "").replace(",", "_")
        fcc_source = get_fcc_args["fcc_source"]
        # Description for calibrate
        if (model is not None and date is None):
            description = (f"{task_name}_{isocode}_"
                           f"{years}_{fcc_source}_"
                           f"{model}")
        # Description for "predict"
        elif (model is not None and date is not None
              and csize_val is None):
            description = (f"{task_name}_{isocode}_"
                           f"{years}_{fcc_source}_"
                           f"{model}_{date}")
        # Description for "validate"
        elif (model is not None and date is not None
              and csize_val is not None):
            description = (f"{task_name}_{isocode}_"
                           f"{years}_{fcc_source}_"
                           f"{model}_{date}_{csize_val}")
        else:
            description = (f"{task_name}_{isocode}_"
                           f"{years}_{fcc_source}")
        return description

    def set_workdir(self, iso, years, fcc_source, seed=None):
        """Set working directory."""
        years = years.replace(" ", "").replace(",", "_")
        random.seed(seed)
        rand_num = random.randint(1, 9999)
        folder_name = f"{iso}_{years}_{fcc_source}_{rand_num:04}"
        if platform.system() == "Windows":
            workdir = os.path.join(os.environ["HOMEDRIVE"],
                                   os.environ["HOMEPATH"],
                                   "deforisk", folder_name)
        else:
            workdir = os.path.join(os.environ["HOME"],
                                   "deforisk", folder_name)
        return workdir

    def make_get_fcc_args(self, aoi, buff, years, fcc_source, perc,
                          tile_size):
        """Make get_ffc_args dictionary."""
        get_fcc_args = {"aoi": aoi, "buff": buff, "years": years,
                        "fcc_source": fcc_source, "perc": perc,
                        "tile_size": tile_size}
        return get_fcc_args

    def get_win_sizes(self):
        """Get window sizes as list."""
        win_sizes = self.args["win_sizes"]
        win_sizes = win_sizes.replace(" ", "").split(",")
        win_sizes = [int(i) for i in win_sizes]
        return win_sizes

    def get_pred_far_models(self):
        """Get list of far models for predictions."""
        pred_far_models = []
        pred_mod = [self.args["pred_icar"],
                    self.args["pred_glm"],
                    self.args["pred_rf"]]
        for (m, far_model) in enumerate(self.FAR_MODELS):
            if pred_mod[m]:
                pred_far_models.append(far_model)
        return pred_far_models

    def get_pred_far_periods(self):
        """Get periods for far predictions."""
        pred_far_periods = []
        pred_date = [self.args["pred_far_t1"],
                     self.args["pred_far_t2"]]
        for (p, period) in enumerate(self.PERIODS):
            if pred_date[p]:
                pred_far_periods.append(period)
        return pred_far_periods

    def get_pred_mw_periods(self):
        """Get periods for mw predictions."""
        pred_mw_periods = []
        pred_dates = [self.args["pred_mw_t1"],
                      self.args["pred_mw_t2"]]
        for (p, period) in enumerate(self.PERIODS):
            if pred_dates[p]:
                pred_mw_periods.append(period)
        return pred_mw_periods

    def get_val_periods(self):
        """Get periods for validation."""
        val_periods = []
        val_dates = [self.args["val_t1"],
                     self.args["val_t2"]]
        for (p, period) in enumerate(self.PERIODS):
            if val_dates[p]:
                val_periods.append(period)
        return val_periods

    def get_date(self, period):
        """Get date from period."""
        date = "t1" if period == "calibration" else "t2"
        return date

    def get_csizes_val(self):
        """Get coarse grid cell sizes as list."""
        csizes_val = self.args["csizes_val"]
        csizes_val = csizes_val.replace(" ", "").split(",")
        csizes_val = [int(i) for i in csizes_val]
        return csizes_val

    def get_val_models(self):
        """Get list of models for validation."""
        val_models = []
        win_sizes = self.get_win_sizes()
        val_far_mod = [self.args["val_icar"],
                       self.args["val_glm"],
                       self.args["val_rf"]]
        if self.args["val_mw"]:
            for win_size in win_sizes:
                val_models.append("mw_" + str(win_size))
        for (m, far_model) in enumerate(self.FAR_MODELS):
            if val_far_mod[m]:
                val_models.append(far_model)
        return val_models

    def get_all_models(self):
        """Get list of all models for comparison."""
        # Be careful here to copy the list to avoid changing FAR_MODELS
        all_models = self.FAR_MODELS.copy()
        win_sizes = self.get_win_sizes()
        for win_size in win_sizes:
            all_models.append("mw_" + str(win_size))
        return all_models

    def create_rmj_calibrate_directory(self):
        """Create rmj calibrate directory."""
        workdir = self.args["workdir"]
        far.make_dir(os.path.join(workdir, "outputs",
                                  "rmj_moving_window"))

    def create_validation_directories(self):
        """Create validation directories."""
        workdir = self.args["workdir"]
        far.make_dir(os.path.join(workdir, "outputs", "validation",
                                  "figures"))
        far.make_dir(os.path.join(workdir, "outputs", "validation",
                                  "tables"))

    def combine_model_results(self):
        """Combine model results for comparison."""
        workdir = self.args["workdir"]
        os.chdir(workdir)
        indices_list = []
        csizes_val = self.get_csizes_val()
        models = self.get_all_models()
        periods = self.PERIODS.copy()
        # Loop on periods and models
        for csize_val in csizes_val:
            for period in periods:
                date = self.get_date(period)
                for model in models:
                    ifile = os.path.join(
                            self.OUT, "validation", "tables",
                            f"indices_{model}_{date}_{csize_val}.csv")
                    if os.path.isfile(ifile):
                        df = pd.read_csv(ifile)
                        df["model"] = model
                        df["period"] = period
                        indices_list.append(df)
        # Concat indices
        indices = pd.concat(indices_list, axis=0)
        indices.sort_values(by=["csize_coarse_grid", "period", "model"])
        indices = indices[["csize_coarse_grid", "csize_coarse_grid_ha",
                           "ncell", "period", "model",
                           "MedAE", "R2", "RMSE", "wRMSE"]]
        indices.to_csv(
            os.path.join(self.OUT, "validation", "indices_all.csv"),
            sep=",", header=True,
            index=False, index_label=False)

    def catch_arguments(self):
        """Catch arguments from UI."""
        # Get variables
        workdir = self.dlg.workdir.text()
        aoi = self.dlg.aoi.text()
        buff = float(self.dlg.buff.text())
        years = self.dlg.years.text()
        fcc_source = self.dlg.fcc_source.text()
        perc = int(self.dlg.perc.text())
        tile_size = float(self.dlg.tile_size.text())
        iso = self.dlg.isocode.text()
        gc_project = self.dlg.gc_project.text()
        wdpa_key = self.dlg.wdpa_key.text()
        proj = self.dlg.proj.text()
        # Sample observations
        nsamp = int(self.dlg.nsamp.text())
        adapt = self.dlg.adapt.isChecked()
        seed = int(self.dlg.seed.text())
        csize = float(self.dlg.csize.text())
        # FAR models
        variables = self.dlg.variables.text()
        beta_start = float(self.dlg.beta_start.text())
        prior_vrho = int(self.dlg.prior_vrho.text())
        mcmc = int((int(self.dlg.mcmc.text()) // 1000) * 1000)
        varselection = self.dlg.varselection.isChecked()
        # FAR predict
        csize_interp = float(self.dlg.csize_interp.text())
        pred_icar = self.dlg.pred_icar.isChecked()
        pred_glm = self.dlg.pred_glm.isChecked()
        pred_rf = self.dlg.pred_rf.isChecked()
        pred_far_t1 = self.dlg.pred_far_t1.isChecked()
        pred_far_t2 = self.dlg.pred_far_t2.isChecked()
        # Rmj model
        defor_thresh = float(self.dlg.defor_thresh.text())
        max_dist = int(self.dlg.max_dist.text())
        win_sizes = self.dlg.win_sizes.text()
        # Rmj predict
        pred_mw_t1 = self.dlg.pred_mw_t1.isChecked()
        pred_mw_t2 = self.dlg.pred_mw_t2.isChecked()
        # Validate
        csizes_val = self.dlg.csizes_val.text()
        val_icar = self.dlg.val_icar.isChecked()
        val_glm = self.dlg.val_glm.isChecked()
        val_rf = self.dlg.val_rf.isChecked()
        val_mw = self.dlg.val_mw.isChecked()
        val_t1 = self.dlg.val_t1.isChecked()
        val_t2 = self.dlg.val_t2.isChecked()
        # Special variables
        if workdir == "":
            seed = 1234  # Only for tests to get same dir
            workdir = self.set_workdir(iso, years, fcc_source, seed)
        get_fcc_args = self.make_get_fcc_args(
            aoi, buff, years, fcc_source, perc, tile_size)
        var = ("C(pa), dist_edge, "
               "dist_road, dist_town, dist_river, "
               "altitude, slope")
        variables = var if variables == "" else variables
        # Dictionary of arguments for far functions
        self.args = {
            "workdir": workdir,
            "get_fcc_args": get_fcc_args,
            "isocode": iso,
            "gc_project": gc_project,
            "wdpa_key": wdpa_key,
            "proj": proj,
            "nsamp": nsamp, "adapt": adapt, "seed": seed,
            "csize": csize, "variables": variables,
            "beta_start": beta_start, "prior_vrho": prior_vrho,
            "mcmc": mcmc, "varselection": varselection,
            "csize_interp": csize_interp, "pred_icar": pred_icar,
            "pred_glm": pred_glm, "pred_rf": pred_rf,
            "pred_far_t1": pred_far_t1, "pred_far_t2": pred_far_t2,
            "defor_thresh": defor_thresh, "max_dist": max_dist,
            "win_sizes": win_sizes,
            "pred_mw_t1": pred_mw_t1, "pred_mw_t2": pred_mw_t2,
            "csizes_val": csizes_val,
            "val_icar": val_icar,
            "val_glm": val_glm, "val_rf": val_rf,
            "val_mw": val_mw,
            "val_t1": val_t1, "val_t2": val_t2,
        }

    def far_get_variables(self):
        """Get variables."""
        self.catch_arguments()
        description = self.task_description("GetVariables")
        task = FarGetVariablesTask(
            description=description,
            iface=self.iface,
            workdir=self.args["workdir"],
            get_fcc_args=self.args["get_fcc_args"],
            isocode=self.args["isocode"],
            gc_project=self.args["gc_project"],
            wdpa_key=self.args["wdpa_key"],
            proj=self.args["proj"])
        # Add task to task manager
        self.tm.addTask(task)

    def far_sample_obs(self):
        """Sample observations."""
        self.catch_arguments()
        description = self.task_description("SampleObs")
        task = FarSampleObsTask(
            description=description,
            iface=self.iface,
            workdir=self.args["workdir"],
            proj=self.args["proj"],
            nsamp=self.args["nsamp"],
            adapt=self.args["adapt"],
            seed=self.args["seed"],
            csize=self.args["csize"])
        # Add task to task manager
        self.tm.addTask(task)

    def far_calibrate(self):
        """Estimate forestatrisk model parameters."""
        self.catch_arguments()
        description = self.task_description("FarCalibrate")
        task = FarCalibrateTask(
            description=description,
            iface=self.iface,
            workdir=self.args["workdir"],
            csize=self.args["csize"],
            variables=self.args["variables"],
            beta_start=self.args["beta_start"],
            prior_vrho=self.args["prior_vrho"],
            mcmc=self.args["mcmc"],
            varselection=self.args["varselection"])
        # Add task to task manager
        self.tm.addTask(task)

    def far_predict(self):
        """Predict deforestation risk."""
        # Catch arguments
        self.catch_arguments()
        pred_far_models = self.get_pred_far_models()
        pred_far_periods = self.get_pred_far_periods()
        # Create tasks with loops on dates and models
        for period in pred_far_periods:
            date = self.get_date(period)
            for model in pred_far_models:
                description = self.task_description(
                    "FarPredict", model, date)
                task = FarPredictTask(
                    description=description,
                    iface=self.iface,
                    workdir=self.args["workdir"],
                    years=self.args["years"],
                    csize=self.args["csize"],
                    csize_interpolate=self.args["csize_interp"],
                    period=period,
                    model=model)
                # Add task to task manager
                self.tm.addTask(task)

    def rmj_calibrate(self):
        """Compute distance threshold and local deforestation rate."""
        # Catch arguments
        self.catch_arguments()
        win_sizes = self.get_win_sizes()
        # Create rmj calibrate directory
        self.create_rmj_calibrate_directory()
        # Loop on window sizes
        for win_size in win_sizes:
            model = f"mv_{win_size}"
            description = self.task_description("RmjCalibrate", model)
            task = RmjCalibrateTask(
                description=description,
                iface=self.iface,
                workdir=self.args["workdir"],
                years=self.args["years"],
                defor_thresh=self.args["defor_thresh"],
                max_dist=self.args["max_dist"],
                win_size=win_size)
            # Add task to task manager
            self.tm.addTask(task)

    def rmj_predict(self):
        """Predict deforestation rate with moving window approach."""
        # Catch arguments
        self.catch_arguments()
        win_sizes = self.get_win_sizes()
        periods = self.get_pred_mw_periods()
        for period in periods:
            date = self.get_date(period)
            for wsize in win_sizes:
                model = f"mv_{wsize}"
                description = self.task_description(
                    "RmjPredict", model, date)
                task = RmjPredictTask(
                    description=description,
                    iface=self.iface,
                    workdir=self.args["workdir"],
                    years=self.args["years"],
                    win_size=wsize,
                    period=period)
                # Add task to task manager
                self.tm.addTask(task)

    def validate(self):
        """Model validation."""
        # Catch arguments
        self.catch_arguments()
        csizes_val = self.get_csizes_val()
        val_models = self.get_val_models()
        val_periods = self.get_val_periods()
        # Create validation directories
        self.create_validation_directories()
        # Main empty task
        description = self.task_description("Validate_all")
        main_task = EmptyTask(description)
        # Tasks with loop on csizes_val, periods, and models
        for csize_val in csizes_val:
            for period in val_periods:
                date = self.get_date(period)
                for model in val_models:
                    description = self.task_description(
                        "Validate", model, date, csize_val)
                    task = ValidateTask(
                        description=description,
                        iface=self.iface,
                        workdir=self.args["workdir"],
                        years=self.args["years"],
                        csize_val=csize_val,
                        period=period,
                        model=model)
                    main_task.addSubTask(task)
        # Combine model results
        main_task.taskCompleted.connect(self.combine_model_results)
        # Add first task to task manager
        self.tm.addTask(main_task)

    def run(self):
        """Run method that performs all the real work."""

        # Create the dialog with elements (after translation)
        # and keep reference.
        # Only create GUI ONCE in callback, so that it will only
        # load when the plugin is started
        if self.first_start is True:
            self.first_start = False
            self.dlg = DeforiskPluginDialog()
            # Set executable path
            self.set_exe_path()

        # Action if buttons ares clicked

        # Data
        self.dlg.run_far_get_variable.clicked.connect(self.far_get_variables)
        self.dlg.run_far_sample.clicked.connect(self.far_sample_obs)

        # FAR with icar, glm, and rf models
        self.dlg.run_far_calibrate.clicked.connect(self.far_calibrate)
        self.dlg.run_far_predict.clicked.connect(self.far_predict)

        # RMJ moving window model
        self.dlg.run_rmj_calibrate.clicked.connect(self.rmj_calibrate)
        self.dlg.run_rmj_predict.clicked.connect(self.rmj_predict)

        # Model validation
        self.dlg.run_validate.clicked.connect(self.validate)

        # Show the dialog
        self.dlg.show()
        result = self.dlg.exec_()
        if result:
            pass

# End of file
