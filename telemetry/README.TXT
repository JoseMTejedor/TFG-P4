En este documento se resumen los pasos necesarios para poner en marcha 
el proyecto

Todas las ejecuciones son desde la carpeta del proyecto

COMPILAR EL PROGRAMA P4

Antes de lanzar el escenario y cada vez que se modifique el fichero telemetry.p4,
recompilar le programa para generar los ficheros utilizados por lo switches BMv2
y el controlador P4Runtime.

- p4c --target bmv2 --arch v1model --p4runtime-files telemetry_p4rt.txt telemetry_.p4


Genera los ficheros telemetry.p4i, telemetry.json y telemetry_p4rt.txt

ARRANCAR EL ESCENARIO MININET:

Poner en marcha la topología

- sudo python escenario_red_final.py 

ABRIR TERMINAR EN H_COL

Esto se hace para configurar el colector y la base de datos

- xterm h_col

Configurar la base de datos en h_col

- sudo python setup_db.py

Configurar colector

- sudo python collector.py

PONER EN MARCHA EL CONTROLADOR:

En otro terminal ejecutar

- sudo python telemetry.py 

AÑADIR EL DISSECTOR AL WIRESHARK:

Para añadir el dissector a Wireshark, abrir Wireshark y acceder a la pestaña Help. Dentro de esta,
entrar en About Wireshark y después en Folders. En esa ventana, buscar la ruta correspondiente a 
Personal Lua Plugins.

Una vez localizada esa carpeta, copiar en ella el fichero - tmt_dissector.lua. Después, cerrar y volver 
a abrir Wireshark. Tras reiniciarlo, Wireshark debería detectar e interpretar la cabecera TMT.

NOTAS:

A veces al hacer Ctrl + C para parar un ping, se sale de mininet. En estos casos 
para parar el escenario:

sudo mn -c