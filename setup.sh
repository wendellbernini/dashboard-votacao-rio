#!/bin/bash
# Instala dependências do sistema necessárias para GeoPandas
apt-get update
apt-get install -y gdal-bin libgdal-dev
export CPLUS_INCLUDE_PATH=/usr/include/gdal
export C_INCLUDE_PATH=/usr/include/gdal
