# Flujo Detallado de Conversación

1. **Saludo**  
   _Ejemplos de input_: "Hola", "¡Quiero hacer un pedido!"  
   - Busca al cliente con `find_customer`.
   - Si no existe, usa `create_customer` y pide datos.
   - Si existe, revisa `get_active_order` y pregunta intención: estado o nuevo pedido.

2. **Datos personales**  
   _Ejemplos_: "Diego Molano, 3214656789, diego@gmail.com"  
   - Registra nombre, teléfono, email, dirección con `update_customer`.
   - Pregunta siguiente acción: ver menú o iniciar pedido.

3. **Consultas de menú**  
   _Ejemplos_: "¿Qué pizzas tienen pepperoni?"  
   - Llama a `get_menu` y filtra según ingredientes o categoría.

4. **Consulta de precios**  
   _Ejemplos_: "¿Cuánto cuesta la pizza medium pepperoni?"  
   - Responde con precio desde la tabla de menú.

5. **Realización / modificación de pedido**  
   _Ejemplos creación_: "1 pizza Large con borde de ajonjolí"  
   _Ejemplos modificación_: "Cambia borde a pimentón"  
   - Usa `upsert_cart` para agregar o actualizar ítems.
   - Confirma subtotal y pide si quiere algo más.

6. **Dirección y pago**  
   _Ejemplos_: "Calle 123 #45-67, Bogotá, Efectivo"  
   - Actualiza pedido con dirección y método de pago.
   - Confirma y pregunta si está listo para cerrar.

7. **Cierre**  
   _Ejemplos_: "Sí, está perfecto", "No"  
   - Si confirma, finaliza flujo y notifica.

8. **No reconocido**  
   - Para cualquier mensaje fuera de lo anterior, responde "No reconocido".