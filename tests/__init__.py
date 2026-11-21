"""Isola os testes do usuário real: config e estado vão para um diretório temporário."""

import os
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="challenger-tests-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_tmp, "config")
os.environ["XDG_DATA_HOME"] = os.path.join(_tmp, "data")
# Virada do dia testada num fuso fixo (sem horário de verão desde 2019).
os.environ["TZ"] = "America/Sao_Paulo"
time.tzset()
