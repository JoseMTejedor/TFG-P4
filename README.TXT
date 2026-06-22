En este documento tiene como objetivo establecer el orden de las distintas
implenetaciones y resumir que se hizo en cada una.

1.- in_time: Primera versión del código, se añade el dato in_time, posterior 
ingress-egress_time como una cabecera. Se hace pasar a esta cabecera, como 
una cabecera MPLS

2.- accum_time: Añade accum_time a la cabecera de telemtría.

3.- link_delay: Añade link_delay a la cabecera de telemetría. También se crea un 
dissector para visualizar la cabecera, ya denominada TMT. Este no genera conflicto con el dissector 
final, ya que se ha usado EtherType 0x88B5. Este es el otro libre, dedicado a experimentación.
Se usa otro, ya que la implenetación final incluye mas datos en la cabecera personalizada

4.- telemetry: Se incluyen todas las cabecera de telemetry en TMT. Se impleneta el sistema de 
clonado de paquetes, el colector y la base de datos

5. routing: IMPLEMENTACIÓN FINAL. Es la que se ha explicado en la memoria.