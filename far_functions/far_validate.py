# -*- coding: utf-8 -*-

# ================================================================
# author          :Ghislain Vieilledent
# email           :ghislain.vieilledent@cirad.fr
# web             :https://ecology.ghislainv.fr
# python_version  :>=3.6
# license         :GPLv3
# ================================================================

"""
Model validation.
"""

import os

from qgis.core import (
    Qgis, QgsTask, QgsMessageLog
)

import pandas as pd
import forestatrisk as far

# Alias
opj = os.path.join


def combine_model_results(workdir, run_models):
    """Combine model results for comparison."""
    os.chdir(workdir)
    indices_list = []
    periods = ["calibration", "validation"]
    models = ["icar", "glm", "rf"]
    # Loop on periods and models
    for period in periods:
        date = "t1" if period == "calibration" else "t2"
        for (model, run_model) in zip(models, run_models):
            if run_model:
                df = pd.read_csv(opj(
                    "outputs",
                    f"indices_{model}_{date}.csv"))
                df["model"] = model
                df["period"] = period
                indices_list.append(df)
    # Concat indices
    indices = pd.concat(indices_list, axis=0)
    indices.sort_values(by=["period", "model"])
    indices = indices[["model", "period", "MedAE", "R2", "wRMSE",
                       "ncell", "csize_coarse_grid",
                       "csize_coarse_grid_ha"]]
    indices.to_csv(
        opj("outputs", "indices_all.csv"),
        sep=",", header=True,
        index=False, index_label=False)


class FarValidateTask(QgsTask):
    """Validating the deforestation risk maps."""

    # Constants
    OUT = "outputs"
    DATA = "data"
    MESSAGE_CATEGORY = "FAR plugin"
    N_STEPS = 1

    def __init__(self, description, iface, workdir, years, period,
                 model):
        super().__init__(description, QgsTask.CanCancel)
        self.iface = iface
        self.workdir = workdir
        self.years = years
        self.period = period
        self.model = model
        self.exception = None

    def get_time_interval(self):
        """Get time intervals from years."""
        years = self.years.replace(" ", "").split(",")
        years = [int(i) for i in years]
        if self.period == "calibration":
            time_interval = years[1] - years[0]
        else:
            time_interval = years[2] - years[1]
        return time_interval

    def set_progress(self, progress, n_steps):
        """Set progress."""
        if progress == 0:
            self.setProgress(1)
        else:
            prog_perc = progress / n_steps
            prog_perc = int(prog_perc * 100)
            self.setProgress(prog_perc)

    def run(self):
        """Model validation."""

        try:
            # Starting message
            msg = 'Started task "{name}"'
            msg = msg.format(name=self.description())
            QgsMessageLog.logMessage(msg, self.MESSAGE_CATEGORY, Qgis.Info)

            # Progress
            progress = 0
            self.set_progress(progress, self.N_STEPS)

            # Set working directory
            os.chdir(self.workdir)

            # Compute time intervals from years
            time_interval = self.get_time_interval()

            # Date
            date = "t1" if self.period == "calibration" else "t2"

            # Validation
            far.validation_udef_arp(
                fcc_file=opj("data", "forest", "fcc123.tif"),
                period=self.period,
                time_interval=time_interval,
                riskmap_file=opj(
                    self.OUT,
                    f"prob_{self.model}_{date}.tif"),
                tab_file_defor=opj(
                    self.OUT,
                    f"defrate_cat_{self.model}_{date}.csv"),
                csize_coarse_grid=50,
                indices_file_pred=opj(
                    self.OUT,
                    f"indices_{self.model}_{date}.csv"),
                tab_file_pred=opj(
                    self.OUT,
                    f"pred_obs_{self.model}_{date}.csv"),
                fig_file_pred=opj(
                    self.OUT,
                    f"pred_obs_{self.model}_{date}.png"),
                verbose=False)

            # Check isCanceled() to handle cancellation
            if self.isCanceled():
                return False

            # Progress
            progress += 1
            self.set_progress(progress, self.N_STEPS)

        except Exception as exc:
            self.exception = exc
            return False

        return True

    def finished(self, result):
        """Show messages and add layers."""

        if result:
            msg = 'Successful task "{name}"'
            msg = msg.format(name=self.description())
            QgsMessageLog.logMessage(msg, self.MESSAGE_CATEGORY, Qgis.Success)

        else:
            if self.exception is None:
                msg = ('FarValidateTask "{name}" not successful but without '
                       'exception (probably the task was manually '
                       'canceled by the user)')
                msg = msg.format(name=self.description())
                QgsMessageLog.logMessage(
                    msg, self.MESSAGE_CATEGORY, Qgis.Warning)
            else:
                msg = 'FarValidateTask "{name}" Exception: {exception}'
                msg = msg.format(
                        name=self.description(),
                        exception=self.exception)
                QgsMessageLog.logMessage(
                    msg, self.MESSAGE_CATEGORY, Qgis.Critical)
                raise self.exception

    def cancel(self):
        """Cancelation message."""
        msg = 'FarValidateTask "{name}" was canceled'
        msg = msg.format(name=self.description())
        QgsMessageLog.logMessage(
            msg, self.MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

# End of file
