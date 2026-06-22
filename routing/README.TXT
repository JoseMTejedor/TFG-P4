En este documento se resumen los pasos necesarios para poner en marcha 
el proyecto

Todas las ejecuciones son desde la carpeta del proyecto

COMPILAR EL PROGRAMA P4

Antes de lanzar el escenario y cada vez que se modifique el fichero telemetry_dynamic.p4,
recompilar le programa para generar los ficheros utilizados por lo switches BMv2
y el controlador P4Runtime.

- p4c --target bmv2 --arch v1model --p4runtime-files telemetry_dynamic_p4rt.txt telemetry_dynamic.p4


Genera los ficheros telemetry_dynamic.p4i, telemetry_dynamic.json y telemetry_dynamic_p4rt.txt

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

Hay dos opciones para poner en marcha el controlador, la basica que no hace un dibujo
del grafo de la red y la que si representa el grafo de la red. Salvo esta diferencia,
ambos codigos hacen lo mismo. Pero se ha querido dejar el codigo sin dibujar el grafo por claridad
y facilitar la comprensión del funcionamiento el controlador. 

Ejecutar estos comandos en un terminar aparte

Controlador sin dibujo grafo:

- sudo python telemetry_dynamic.py 

Controlador con dibujo grafo:

- sudo python telemetry_grafo.py 

En la segunda opción, el grafo se genera como una imagen llamada grafo_dinamico.png dentro del 
directorio de ejecución. Esta imagen debería actualizarse automáticamente cada cierto intervalo 
de tiempo, o cada vez que se detecte una nueva comunicación. No obstante, si el ordenador donde 
se lanza la ejecución no tiene suficiente capacidad o se sobrecalienta, puede ser necesario cerrar 
y volver a abrir la imagen para visualizar la versión actualizada.

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