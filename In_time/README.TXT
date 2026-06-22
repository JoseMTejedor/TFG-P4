En este documento se resumen los pasos necesarios para poner en marcha 
el proyecto

Todas las ejecuciones son desde la carpeta del proyecto

COMPILAR EL PROGRAMA P4

Antes de lanzar el escenario y cada vez que se modifique el fichero telemetry.p4,
recompilar le programa para generar los ficheros utilizados por lo switches BMv2
y el controlador P4Runtime.

- p4c --target bmv2 --arch v1model --p4runtime-files in_time_p4rt.txt in_time.p4


Genera los ficheros in_time.p4i, in_time.json y in_time_p4rt.txt.

ARRANCAR EL ESCENARIO MININET:

Poner en marcha la topología

- sudo python escenario_red.py 


PONER EN MARCHA EL CONTROLADOR:

En otro terminal ejecutar

- sudo python in_time.py 

NOTAS:

A veces al hacer Ctrl + C para parar un ping, se sale de mininet. En estos casos 
para parar el escenario:

sudo mn -c