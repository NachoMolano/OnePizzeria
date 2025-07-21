# Configuración de Base de Datos para Smart Memory

## 🗄️ Crear la tabla en Supabase

1. **Ve a tu proyecto Supabase**:
   - Accede a https://supabase.com/dashboard
   - Selecciona tu proyecto de la pizzería

2. **Abre el SQL Editor**:
   - En el menú lateral, haz clic en "SQL Editor"
   - Crea una nueva query

3. **Ejecuta el script**:
   - Copia todo el contenido de `database/smart_memory_schema.sql`
   - Pégalo en el editor SQL
   - Haz clic en "Run" para ejecutar

4. **Verifica la creación**:
   - Ve a "Table Editor" 
   - Deberías ver la nueva tabla `smart_conversation_memory`

## 📊 Estructura de la tabla

La tabla `smart_conversation_memory` contiene:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `thread_id` | TEXT (PK) | ID único del usuario/conversación |
| `customer_context` | JSONB | Contexto clave del cliente |
| `recent_messages` | JSONB | Mensajes recientes (ventana deslizante) |
| `session_metadata` | JSONB | Metadatos adicionales de la sesión |
| `last_activity` | TIMESTAMP | Última actividad (auto-actualizado) |
| `created_at` | TIMESTAMP | Fecha de creación |

## 🔍 Ventajas de este diseño

1. **Escalable**: Maneja miles de conversaciones simultáneas
2. **Eficiente**: Ventana deslizante de mensajes (máximo 12)
3. **Inteligente**: Auto-limpieza de conversaciones viejas
4. **Rápido**: Índices optimizados para consultas frecuentes
5. **Flexible**: JSONB permite estructuras de datos dinámicas

## 🧹 Mantenimiento automático

- **Trigger**: Actualiza `last_activity` automáticamente
- **TTL**: Conversaciones se limpian después de 7 días de inactividad
- **Cache**: Sistema de cache en memoria para mejor rendimiento

## 🚀 ¿Listo para continuar?

Una vez hayas ejecutado el SQL en Supabase, podemos continuar con la integración del sistema de memoria inteligente. 