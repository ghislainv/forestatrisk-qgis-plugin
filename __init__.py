# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ForestatriskPlugin
                                 A QGIS plugin
 Deforestation risk mapping.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2023-12-13
        copyright            : (C) 2023 by Ghislain Vieilledent (Cirad)
        email                : ghislain.vieilledent@cirad.fr
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load ForestatriskPlugin class from file ForestatriskPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .forestatrisk_plugin import ForestatriskPlugin
    return ForestatriskPlugin(iface)
