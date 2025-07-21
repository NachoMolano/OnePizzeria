#!/usr/bin/env python3
"""
Bot de Telegram - Asistente de Compras
======================================
Bot robusto para gestión de compras, descuentos y recetas.
Funcionalidades:
1. Búsqueda de precios de productos
2. Newsletter de descuentos diarios
3. Análisis de precios para recetas
4. Gestión de órdenes de pastelería
"""

import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional

from dotenv import load_dotenv
from src import duck_session, storage
from src.discount_scrapers.carulla_discount_scraper_selenium import \
    CarullaDiscountScraperSelenium
from src.discount_scrapers.exito_discount_scraper import ExitoDiscountScraper
from src.discount_scrapers.jumbo_discount_scraper import JumboDiscountScraper
from src.scraper_manager import ScraperManager
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      KeyboardButton, ReplyKeyboardMarkup, Update)
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                          ContextTypes, ConversationHandler, MessageHandler,
                          filters)

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Vuelto a INFO para menos ruido
)
logger = logging.getLogger(__name__)

# Logger específico para debugging del ConversationHandler (solo cuando sea necesario)
debug_logger = logging.getLogger('conversation_debug')
debug_logger.setLevel(logging.WARNING)  # Solo errores importantes

# Cargar variables de entorno
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Estados de conversación
class BotState(Enum):
    MAIN_MENU = 0
    PRICE_SEARCH = 1
    RECIPE_INPUT = 2
    RECIPE_INGREDIENTS = 3
    BAKERY_ORDER = 4
    NEWSLETTER_CONFIG = 5
    DISCOUNT_SEARCH = 6  # Nuevo estado para descuentos

# Estados específicos para búsqueda de precios
PRODUCT_INPUT, STORE_SELECTION = range(3, 5)

# Estados para recetas
RECIPE_NAME, INGREDIENT_LIST, RECIPE_ANALYSIS = range(5, 8)

# Estados para órdenes de pastelería
ORDER_TYPE, ORDER_DETAILS, ORDER_SCHEDULE = range(8, 11)

# Estados para descuentos
DISCOUNT_STORE_SELECTION = range(11, 12)

class ShoppingBot:
    def __init__(self):
        self.user_data: Dict = {}
        self.stores = ["Jumbo", "Éxito", "Carulla", "Todos los supermercados"]
        self.scraper_manager = None  # Se inicializará cuando se necesite
        self.warehouse_enabled = False
        
        # Inicializar data warehouse
        try:
            storage.init_warehouse()
            duck_session.register_parquet_views()
            self.warehouse_enabled = True
            logger.info("Data warehouse inicializado correctamente")
        except Exception as e:
            logger.error(f"Error inicializando data warehouse: {e}")
            self.warehouse_enabled = False
        
        # Patrones de emoji mejorados para debugging
        self.emoji_patterns = {
            "search": [
                r"^🔍\ufe0f?\s*Buscar Precios$",
                r"^🔍\s*Buscar Precios$",
                r"^Buscar Precios$",
                r".*Buscar.*Precios.*"
            ],
            "discounts": [
                r"^📢\ufe0f?\s*Descuentos$",
                r"^📢\s*Descuentos$",
                r"^Descuentos$",
                r".*Descuentos.*"
            ],
            "recipe": [
                r"^👨‍🍳\ufe0f?\s*Analizar Receta$",
                r"^👨‍🍳\s*Analizar Receta$", 
                r"^Analizar Receta$",
                r".*Analizar.*Receta.*"
            ],
            "newsletter": [
                r"^📰\ufe0f?\s*Newsletter$",
                r"^📰\s*Newsletter$",
                r"^Newsletter$",
                r".*Newsletter.*"
            ],
            "bakery": [
                r"^🧁\ufe0f?\s*Órdenes Pastelería$",
                r"^🧁\s*Órdenes Pastelería$",
                r"^Órdenes Pastelería$",
                r".*Órdenes.*Pastelería.*"
            ],
            "settings": [
                r"^⚙️\ufe0f?\s*Configuración$",
                r"^⚙️\s*Configuración$",
                r"^Configuración$",
                r".*Configuración.*"
            ],
            "help": [
                r"^❓\ufe0f?\s*Ayuda$",
                r"^❓\s*Ayuda$",
                r"^Ayuda$",
                r".*Ayuda.*"
            ]
        }
        
    def analyze_text(self, text: str) -> Dict:
        """Analiza un texto para debugging de caracteres especiales"""
        analysis = {
            'original': text,
            'repr': repr(text),
            'length': len(text),
            'unicode_points': [f"U+{ord(c):04X}" for c in text],
            'unicode_names': [],
            'has_variation_selector': '\ufe0f' in text,
            'has_zwj': '\u200d' in text,
            'pattern_matches': {}
        }
        
        # Nombres Unicode
        for char in text:
            try:
                name = unicodedata.name(char)
                analysis['unicode_names'].append(f"{char} = {name}")
            except ValueError:
                analysis['unicode_names'].append(f"{char} = <no name>")
        
        # Probar patrones
        for category, patterns in self.emoji_patterns.items():
            analysis['pattern_matches'][category] = []
            for pattern in patterns:
                match = re.match(pattern, text)
                analysis['pattern_matches'][category].append({
                    'pattern': pattern,
                    'matches': bool(match)
                })
        
        return analysis
    
    async def debug_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler de debugging para analizar mensajes (solo cuando sea necesario)"""
        if not update.message or not update.message.text:
            return
            
        text = update.message.text
        # Solo logear si hay problemas o si se activa debug específicamente
        if debug_logger.isEnabledFor(logging.DEBUG):
            analysis = self.analyze_text(text)
            debug_logger.debug(f"Mensaje: {analysis['original']} | VS-16: {analysis['has_variation_selector']}")
    
    async def test_patterns(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando para probar patrones de emoji"""
        test_strings = [
            "🔍 Buscar Precios",
            "🔍\ufe0f Buscar Precios", 
            "👨‍🍳 Analizar Receta",
            "📰 Newsletter",
            "🧁 Órdenes Pastelería",
            "⚙️ Configuración",
            "❓ Ayuda"
        ]
        
        results = []
        for test_str in test_strings:
            analysis = self.analyze_text(test_str)
            results.append(f"**{test_str}**")
            results.append(f"Unicode: {' '.join(analysis['unicode_points'])}")
            results.append(f"VS-16: {analysis['has_variation_selector']}")
            results.append("")
        
        await update.message.reply_text(
            "🧪 **Prueba de Patrones de Emoji**\n\n" + "\n".join(results),
            parse_mode='Markdown'
        )
    
    async def show_warehouse_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Muestra estadísticas del data warehouse"""
        if not self.warehouse_enabled:
            await update.message.reply_text(
                "❌ Data warehouse no está disponible",
                parse_mode='Markdown'
            )
            return
        
        try:
            # Obtener estadísticas del warehouse
            stats = storage.get_warehouse_stats()
            
            # Obtener estadísticas adicionales de DuckDB
            try:
                schema_info = duck_session.get_schema_info()
                product_count = schema_info.get('counts', {}).get('products', 0)
                price_count = schema_info.get('counts', {}).get('prices', 0)
            except:
                product_count = stats.get('products_count', 0)
                price_count = stats.get('price_records_count', 0)
            
            # Formatear estadísticas
            stats_text = f"""
📊 **Estadísticas del Data Warehouse**

**Productos almacenados:** {product_count:,}
**Registros de precios:** {price_count:,}
**Tiendas activas:** {', '.join(stats.get('stores', []))}

**Directorio:** `{stats.get('warehouse_dir', 'N/A')}`
"""
            
            if stats.get('date_range'):
                date_range = stats['date_range']
                stats_text += f"**Rango de fechas:** {date_range['min']} - {date_range['max']}\n"
            
            # Obtener resumen de precios recientes
            try:
                recent_summary = duck_session.get_price_summary()
                if not recent_summary.empty:
                    stats_text += "\n**Resumen reciente:**\n"
                    for _, row in recent_summary.head(5).iterrows():
                        stats_text += f"• {row['store_id']}: {row['products_count']} productos (${row['avg_price']:.0f} promedio)\n"
            except Exception as e:
                logger.debug(f"Error obteniendo resumen de precios: {e}")
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            await update.message.reply_text(
                "❌ Error obteniendo estadísticas del warehouse",
                parse_mode='Markdown'
            )
    
    async def query_warehouse(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Permite consultar productos en el warehouse"""
        if not self.warehouse_enabled:
            await update.message.reply_text(
                "❌ Data warehouse no está disponible",
                parse_mode='Markdown'
            )
            return
        
        # Obtener argumentos del comando
        args = context.args
        if not args:
            await update.message.reply_text(
                "📊 **Consulta de Warehouse**\n\n"
                "Uso: `/warehouse <término_búsqueda>`\n\n"
                "Ejemplos:\n"
                "• `/warehouse aceite`\n"
                "• `/warehouse pan bimbo`\n"
                "• `/warehouse sal`",
                parse_mode='Markdown'
            )
            return
        
        search_term = ' '.join(args).lower()
        
        try:
            # Buscar productos en el warehouse
            query = f"""
            SELECT DISTINCT
                p.name,
                p.store_id,
                p.brand,
                p.category,
                pr.price_final,
                pr.discount_pct,
                pr.date
            FROM v_product p
            JOIN v_price pr ON p.product_id = pr.product_id AND p.store_id = pr.store_id
            WHERE LOWER(p.name) LIKE '%{search_term}%'
            ORDER BY pr.date DESC, pr.price_final ASC
            LIMIT 10
            """
            
            results = duck_session.execute_query(query)
            
            if results.empty:
                await update.message.reply_text(
                    f"❌ No se encontraron productos para '{search_term}' en el warehouse",
                    parse_mode='Markdown'
                )
                return
            
            # Formatear resultados
            response = f"🔍 **Resultados para '{search_term}'**\n\n"
            
            for _, row in results.iterrows():
                name = row['name'][:50] + "..." if len(row['name']) > 50 else row['name']
                store = row['store_id'].title()
                price = f"${row['price_final']:,.0f}"
                discount = f" ({row['discount_pct']:.0f}% desc.)" if row['discount_pct'] > 0 else ""
                date = row['date']
                
                response += f"• **{name}**\n"
                response += f"  🏪 {store} | 💰 {price}{discount}\n"
                response += f"  📅 {date}\n\n"
            
            await update.message.reply_text(response, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error consultando warehouse: {e}")
            await update.message.reply_text(
                "❌ Error consultando el warehouse",
                parse_mode='Markdown'
            )
    
    async def universal_message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handler universal que captura todos los mensajes para debugging"""
        if not update.message or not update.message.text:
            return ConversationHandler.END
        
        text = update.message.text.strip()
        user_id = update.effective_user.id
        
        # Debug del mensaje
        await self.debug_message(update, context)
        
        # Intentar coincidencias flexibles
        if "buscar" in text.lower() and "precio" in text.lower():
            return await self.start_price_search(update, context)
        elif "descuento" in text.lower():
            return await self.start_discount_search(update, context)
        elif "analizar" in text.lower() and "receta" in text.lower():
            return await self.start_recipe_analysis(update, context)
        elif "newsletter" in text.lower():
            return await self.configure_newsletter(update, context)
        elif "orden" in text.lower() and "pastel" in text.lower():
            return await self.start_bakery_orders(update, context)
        elif "config" in text.lower():
            return await self.show_settings(update, context)
        elif "ayuda" in text.lower():
            return await self.show_help(update, context)
        else:
            # Mensaje no reconocido - respuesta más limpia
            await update.message.reply_text(
                f"❓ No entendí tu mensaje. Usa /start para ver el menú principal.",
                parse_mode='Markdown'
            )
            return BotState.MAIN_MENU.value
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Comando /start - Menú principal con opciones múltiples"""
        user = update.effective_user
        logger.info(f"Usuario {user.first_name} ({user.id}) inició el bot")
        
        # Inicializar datos del usuario
        if user.id not in self.user_data:
            self.user_data[user.id] = {
                'preferences': {},
                'recipes': [],
                'orders': [],
                'newsletter_enabled': False
            }
        
        welcome_text = f"""🛒 **¡Hola {user.first_name}!** 

Soy tu Asistente de Compras inteligente. Te ayudo con:

🔍 **Búsqueda de precios** - Encuentra los mejores precios
📢 **Descuentos** - Ofertas y promociones actuales
📰 **Newsletter diario** - Descuentos a las 7:00 AM
👨‍🍳 **Análisis de recetas** - Precios de ingredientes
🧁 **Órdenes de pastelería** - Gestión de insumos

¿Qué te gustaría hacer?"""

        # Teclado principal con emojis
        keyboard = [
            [KeyboardButton("🔍 Buscar Precios"), KeyboardButton("📢 Descuentos")],
            [KeyboardButton("👨‍🍳 Analizar Receta"), KeyboardButton("📰 Newsletter")],
            [KeyboardButton("🧁 Órdenes Pastelería")],
            [KeyboardButton("⚙️ Configuración"), KeyboardButton("❓ Ayuda")]
        ]
        
        # Teclado alternativo inline como respaldo
        inline_keyboard = [
            [InlineKeyboardButton("🔍 Buscar Precios", callback_data="menu_search")],
            [InlineKeyboardButton("📢 Descuentos", callback_data="menu_discounts")],
            [InlineKeyboardButton("👨‍🍳 Analizar Receta", callback_data="menu_recipe")],
            [InlineKeyboardButton("📰 Newsletter", callback_data="menu_newsletter")],
            [InlineKeyboardButton("🧁 Órdenes Pastelería", callback_data="menu_bakery")],
            [InlineKeyboardButton("⚙️ Configuración", callback_data="menu_settings")],
            [InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")]
        ]
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        inline_markup = InlineKeyboardMarkup(inline_keyboard)
        
        # Enviar ambos menús
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
        await update.message.reply_text(
            "**Menú alternativo (inline):**\nSi los botones de arriba no funcionan, usa estos:",
            reply_markup=inline_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"Menú principal enviado, estado: {BotState.MAIN_MENU.value}")
        return BotState.MAIN_MENU.value

    async def start_price_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia el flujo de búsqueda de precios"""
        logger.info("Mostrando opciones de búsqueda de precios")
        
        keyboard = [
            [InlineKeyboardButton("📱 Producto individual", callback_data="search_single")],
            [InlineKeyboardButton("📋 Lista de productos", callback_data="search_list")],
            [InlineKeyboardButton("🏪 Comparar tiendas", callback_data="search_compare")],
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = "🔍 **Búsqueda de Precios**\n\n¿Qué tipo de búsqueda quieres realizar?"
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
                    await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return BotState.MAIN_MENU.value



    async def handle_product_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Procesa la entrada de productos"""
        products = update.message.text.strip()
        context.user_data['products'] = products
        
        search_type = context.user_data.get('search_type', 'search_single')
        
        if search_type in ['search_single', 'search_compare']:
            # Para producto individual o comparación, mostrar selector de tienda
            keyboard = []
            for store in self.stores:
                keyboard.append([InlineKeyboardButton(store, callback_data=f"store_{store}")])
            keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="back_search")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"🏪 **Selecciona la tienda:**\n\nProducto: `{products}`",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return STORE_SELECTION
        else:
            # Para lista de productos, buscar en todas las tiendas
            return await self.execute_search(update, context, "Todos los supermercados")

    async def handle_store_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja la selección de tienda"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back_search":
            return await self.start_price_search(update, context)
        
        store = query.data.replace("store_", "")
        return await self.execute_search(update, context, store)

    async def execute_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, store: str) -> int:
        """Ejecuta la búsqueda de precios usando los scrapers reales"""
        products = context.user_data.get('products', '')
        search_type = context.user_data.get('search_type', 'search_single')
        
        # Mensaje de búsqueda en progreso
        if hasattr(update, 'callback_query') and update.callback_query:
            message = await update.callback_query.edit_message_text(
                f"🔍 Buscando precios...\n\n📦 Productos: `{products}`\n🏪 Tienda: `{store}`",
                parse_mode='Markdown'
            )
        else:
            message = await update.message.reply_text(
                f"🔍 Buscando precios...\n\n📦 Productos: `{products}`\n🏪 Tienda: `{store}`",
                parse_mode='Markdown'
            )
        
        try:
            # Obtener el ScraperManager (se crea si es necesario)
            scraper_manager = self._get_scraper_manager()
            
            # Determinar tienda para el scraper
            store_mapping = {
                "Jumbo": "jumbo",
                "Éxito": "exito", 
                "Carulla": "carulla",
                "Todos los supermercados": None
            }
            target_store = store_mapping.get(store)
            
            if search_type == "search_list":
                # Buscar múltiples productos - soportar comas y saltos de línea
                # Primero dividir por saltos de línea, luego por comas
                products_raw = products.replace('\n', ',').replace('\r', ',')
                product_list = [p.strip() for p in products_raw.split(',') if p.strip()]
                
                if not product_list:
                    await update.message.reply_text(
                        "❌ No se encontraron productos válidos. Intenta de nuevo con el formato correcto.",
                        parse_mode='Markdown'
                    )
                    return BotState.MAIN_MENU.value
                
                results = await scraper_manager.search_product_list(product_list, target_store)
                
                # Formatear resultados para múltiples productos
                result_text = f"✅ **Resultados de búsqueda para {len(product_list)} productos**\n\n"
                
                for product_query, store_results in results.items():
                    result_text += f"📦 **{product_query}**\n"
                    best_prices = scraper_manager.find_best_prices(store_results)
                    
                    if best_prices['found']:
                        best = best_prices['best_deal']
                        result_text += f"💰 Mejor precio: {best['product']['precio_final']} ({best['store']})\n"
                        if len(best_prices['all_deals']) > 1:
                            result_text += f"📊 {len(best_prices['all_deals'])} opciones encontradas\n"
                    else:
                        result_text += "❌ No se encontraron precios\n"
                    result_text += "\n"
                
            elif search_type == "search_compare":
                # Comparar precios entre tiendas
                results = await scraper_manager.search_single_product(products, None)
                result_text = scraper_manager.format_comparison_results(results, products)
                
            else:
                # Búsqueda simple
                results = await scraper_manager.search_single_product(products, target_store)
                result_text = scraper_manager.format_search_results(results, products)
            
        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            result_text = f"❌ **Error en la búsqueda**\n\nOcurrió un problema al buscar los productos. Por favor, intenta de nuevo más tarde.\n\n📦 Productos: `{products}`\n🏪 Tienda: `{store}`"
        
        # Botones de acción
        keyboard = [
            [InlineKeyboardButton("🔍 Nueva búsqueda", callback_data="new_search")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.edit_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
        return BotState.MAIN_MENU.value

    async def start_recipe_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia el análisis de recetas"""
        await update.message.reply_text(
            "👨‍🍳 **Análisis de Receta**\n\n¿Cuál es el nombre de tu receta?",
            parse_mode='Markdown'
        )
        return RECIPE_NAME

    async def handle_recipe_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja el nombre de la receta"""
        recipe_name = update.message.text.strip()
        context.user_data['recipe_name'] = recipe_name
        
        await update.message.reply_text(
            f"📝 **Receta: {recipe_name}**\n\nAhora escribe los ingredientes separados por comas:\n\n*Ejemplo: 2 huevos, 200g harina, 100ml leche, 50g azúcar*",
            parse_mode='Markdown'
        )
        return INGREDIENT_LIST

    async def handle_ingredient_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Procesa la lista de ingredientes"""
        ingredients = update.message.text.strip()
        recipe_name = context.user_data.get('recipe_name', 'Receta')
        
        # Simular análisis
        await update.message.reply_text(
            f"🔍 Analizando precios para: **{recipe_name}**\n\nIngredientes: `{ingredients}`",
            parse_mode='Markdown'
        )
        
        await asyncio.sleep(2)
        
        # Resultado placeholder
        result_text = f"""
        ✅ **Análisis completo: {recipe_name}**

        🛒 **Mejor estrategia de compra:**

        **Jumbo** (Total: $15,670)
        • 2 huevos - $8,900/docena
        • Harina 200g - $3,200/kg
        • Leche 100ml - $2,890/L
        • Azúcar 50g - $680/kg

        💰 **Costo por porción:** $3,918
        🏪 **Tienda recomendada:** Jumbo
        💡 **Descuentos disponibles:** 15% en lácteos

        ¿Quieres guardar esta receta?
                """
        
        keyboard = [
            [InlineKeyboardButton("💾 Guardar receta", callback_data="save_recipe")],
            [InlineKeyboardButton("🛒 Crear lista de compras", callback_data="create_shopping_list")],
            [InlineKeyboardButton("👨‍🍳 Nueva receta", callback_data="new_recipe")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(result_text, reply_markup=reply_markup, parse_mode='Markdown')
        return BotState.MAIN_MENU.value

    async def configure_newsletter(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Configura el newsletter de descuentos"""
        user_id = update.effective_user.id
        current_status = self.user_data.get(user_id, {}).get('newsletter_enabled', False)
        status_text = "✅ Activado" if current_status else "❌ Desactivado"
        
        keyboard = [
            [InlineKeyboardButton("🔔 Activar newsletter", callback_data="newsletter_on")],
            [InlineKeyboardButton("🔕 Desactivar newsletter", callback_data="newsletter_off")],
            [InlineKeyboardButton("⏰ Cambiar horario", callback_data="newsletter_time")],
            [InlineKeyboardButton("🏪 Seleccionar tiendas", callback_data="newsletter_stores")],
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""
        📰 **Newsletter de Descuentos**

        **Estado actual:** {status_text}
        **Horario:** 7:00 AM (Colombia)
        **Tiendas:** Todas

        El newsletter te enviará cada día:
        • 💰 Mejores descuentos del día
        • 🏪 Comparación de precios
        • 🎯 Ofertas personalizadas
        • 📊 Tendencias de precios

        ¿Qué quieres configurar?
                """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return BotState.MAIN_MENU.value

    async def start_discount_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia el flujo de búsqueda de descuentos"""
        logger.info("Mostrando opciones de búsqueda de descuentos")
        
        keyboard = [
            [InlineKeyboardButton("🏬 Jumbo", callback_data="discount_jumbo")],
            [InlineKeyboardButton("🟢 Éxito", callback_data="discount_exito")],
            [InlineKeyboardButton("🔵 Carulla", callback_data="discount_carulla")],
            [InlineKeyboardButton("🌟 Todos los supermercados", callback_data="discount_all")],
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = """📢 **Descuentos y Ofertas**

Busca las mejores ofertas y descuentos actuales. Selecciona la tienda que te interesa:

🏬 **Jumbo** - Ofertas y promociones especiales
🟢 **Éxito** - Descuentos y colecciones
🔵 **Carulla** - Promociones y ofertas selectas
🌟 **Todos** - Comparar todas las tiendas

¿De qué tienda quieres ver los descuentos?"""
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        return BotState.DISCOUNT_SEARCH.value

    async def handle_discount_store_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja la selección de tienda para descuentos"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back_main":
            return await self.back_to_main(update, context)
        
        store_mapping = {
            "discount_jumbo": "jumbo",
            "discount_exito": "exito", 
            "discount_carulla": "carulla",
            "discount_all": "all"
        }
        
        selected_store = store_mapping.get(query.data)
        if not selected_store:
            await query.edit_message_text("❌ Selección no válida. Usa /start para volver al menú.")
            return BotState.MAIN_MENU.value
        
        # Mensaje de búsqueda en progreso
        if selected_store == "all":
            await query.edit_message_text(
                "🔍 **Buscando descuentos en todas las tiendas...**\n\n⏳ Esto puede tomar unos momentos",
                parse_mode='Markdown'
            )
        else:
            store_names = {"jumbo": "Jumbo", "exito": "Éxito", "carulla": "Carulla"}
            await query.edit_message_text(
                f"🔍 **Buscando descuentos en {store_names[selected_store]}...**\n\n⏳ Obteniendo ofertas actuales",
                parse_mode='Markdown'
            )
        
        return await self.execute_discount_search(update, context, selected_store)

    async def execute_discount_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, store: str) -> int:
        """Ejecuta la búsqueda de descuentos usando los scrapers"""
        try:
            all_discounts = []
            
            if store == "all" or store == "exito":
                try:
                    logger.info("Scrapeando descuentos de Éxito...")
                    exito_scraper = ExitoDiscountScraper()
                    exito_discounts = exito_scraper.scrape_discounts()
                    all_discounts.extend(exito_discounts)
                    exito_scraper.close()
                except Exception as e:
                    logger.error(f"Error scrapeando Éxito: {e}")
            
            if store == "all" or store == "carulla":
                try:
                    logger.info("Scrapeando descuentos de Carulla...")
                    carulla_scraper = CarullaDiscountScraperSelenium(headless=True)
                    carulla_discounts = carulla_scraper.scrape_discounts()
                    all_discounts.extend(carulla_discounts)
                    carulla_scraper.close()
                except Exception as e:
                    logger.error(f"Error scrapeando Carulla: {e}")
            
            if store == "all" or store == "jumbo":
                try:
                    logger.info("Scrapeando descuentos de Jumbo...")
                    jumbo_scraper = JumboDiscountScraper()
                    jumbo_discounts = jumbo_scraper.scrape_discounts()
                    all_discounts.extend(jumbo_discounts)
                    jumbo_scraper.close()
                except Exception as e:
                    logger.error(f"Error scrapeando Jumbo: {e}")
            
            # Formatear resultados
            if all_discounts:
                result_text = self._format_discount_results(all_discounts, store)
            else:
                result_text = "❌ No se encontraron descuentos en este momento.\n\nPrueba de nuevo más tarde o selecciona otra tienda."
            
            # Agregar botones para nuevas búsquedas
            keyboard = [
                [InlineKeyboardButton("🔄 Buscar otra tienda", callback_data="menu_discounts")],
                [InlineKeyboardButton("🔍 Buscar precios", callback_data="menu_search")],
                [InlineKeyboardButton("🏠 Menú principal", callback_data="back_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Enviar resultado (puede ser largo, así que usar texto plano)
            await update.callback_query.edit_message_text(
                result_text[:4096],  # Telegram tiene límite de 4096 caracteres
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error ejecutando búsqueda de descuentos: {e}")
            await update.callback_query.edit_message_text(
                f"❌ Error al buscar descuentos: {str(e)}\n\nInténtalo de nuevo más tarde.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Volver", callback_data="menu_discounts")
                ]])
            )
        
        return BotState.MAIN_MENU.value

    def _format_discount_results(self, discounts: list, store: str) -> str:
        """Formatea los resultados de descuentos para mostrar en el bot"""
        if not discounts:
            return "❌ No se encontraron descuentos."
        
        total = len(discounts)
        store_names = {"jumbo": "Jumbo", "exito": "Éxito", "carulla": "Carulla", "all": "todas las tiendas"}
        store_name = store_names.get(store, store)
        
        result_text = f"🎉 **{total} descuentos encontrados en {store_name}**\n\n"
        
        # Mostrar top 10 descuentos
        for i, discount in enumerate(discounts[:10]):
            name = discount.get('name', 'Sin nombre')[:50]
            store_info = discount.get('store', 'N/A')
            discount_pct = discount.get('discount_percentage')
            collection_url = discount.get('collection_url', '')
            
            result_text += f"**{i+1}. {name}**\n"
            result_text += f"🏪 {store_info.title()}"
            
            if discount_pct:
                result_text += f" | 💰 {discount_pct}% OFF"
            
            if collection_url:
                result_text += f"\n🔗 [Ver ofertas]({collection_url})"
            
            result_text += "\n\n"
        
        if total > 10:
            result_text += f"... y {total - 10} descuentos más\n\n"
        
        result_text += "💡 **Tip:** Usa 'Buscar Precios' para comparar productos específicos."
        
        return result_text

    async def start_bakery_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Inicia la gestión de órdenes de pastelería"""
        keyboard = [
            [InlineKeyboardButton("📋 Ver órdenes pendientes", callback_data="view_orders")],
            [InlineKeyboardButton("➕ Nueva orden", callback_data="new_order")],
            [InlineKeyboardButton("📅 Programar compras", callback_data="schedule_purchases")],
            [InlineKeyboardButton("📊 Análisis de costos", callback_data="cost_analysis")],
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = """
        🧁 **Gestión de Pastelería**

        Optimiza tus compras de insumos:
        • 📋 Gestiona órdenes pendientes
        • 🛒 Programa compras automáticas
        • 💰 Aprovecha descuentos
        • 📊 Analiza costos y tendencias

        ¿Qué quieres hacer?
                """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return BotState.MAIN_MENU.value

    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Muestra configuraciones del bot"""
        keyboard = [
            [InlineKeyboardButton("🏪 Tiendas favoritas", callback_data="fav_stores")],
            [InlineKeyboardButton("📍 Ubicación", callback_data="location")],
            [InlineKeyboardButton("💰 Presupuesto", callback_data="budget")],
            [InlineKeyboardButton("🔔 Notificaciones", callback_data="notifications")],
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚙️ **Configuración**\n\nPersonaliza tu experiencia:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return BotState.MAIN_MENU.value

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Muestra ayuda del bot"""
        help_text = """
        ❓ **Ayuda - Asistente de Compras**

        **🔍 Búsqueda de precios:**
        • Producto individual: busca un solo producto
        • Lista de productos: busca varios productos
        • Comparar tiendas: compara precios entre tiendas

        **👨‍🍳 Análisis de recetas:**
        • Calcula costos de ingredientes
        • Encuentra mejores precios
        • Sugiere tiendas óptimas

        **📰 Newsletter:**
        • Descuentos diarios a las 7:00 AM
        • Ofertas personalizadas
        • Comparaciones de precios

        **🧁 Órdenes de pastelería:**
        • Gestiona inventario de insumos
        • Programa compras automáticas
        • Optimiza costos

        **Comandos disponibles:**
        /start - Menú principal
        /help - Esta ayuda
        /cancel - Cancelar operación actual

        ¿Necesitas más ayuda? Escríbeme cualquier duda.
                """
        
        keyboard = [[InlineKeyboardButton("🏠 Menú principal", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        return BotState.MAIN_MENU.value

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja todas las callback queries incluyendo menú inline"""
        query = update.callback_query
        await query.answer()
        
        # Debug para identificar el problema
        logger.info(f"Callback recibido: {query.data}")
        
        # Menú inline handlers
        if query.data == "menu_search":
            logger.info("Iniciando búsqueda de precios")
            return await self.start_price_search(update, context)
        elif query.data == "menu_discounts":
            logger.info("Iniciando búsqueda de descuentos")
            return await self.start_discount_search(update, context)
        elif query.data == "menu_recipe":
            return await self.start_recipe_analysis(update, context)
        elif query.data == "menu_newsletter":
            return await self.configure_newsletter(update, context)
        elif query.data == "menu_bakery":
            return await self.start_bakery_orders(update, context)
        elif query.data == "menu_settings":
            return await self.show_settings(update, context)
        elif query.data == "menu_help":
            return await self.show_help(update, context)
        elif query.data == "test_patterns":
            await self.test_patterns(update, context)
            return BotState.MAIN_MENU.value
        
        # Callbacks de búsqueda de precios
        elif query.data == "search_single":
            context.user_data['search_type'] = query.data
            text = "📱 **Producto Individual**\n\nEscribe el nombre del producto que quieres buscar:"
            await query.edit_message_text(text, parse_mode='Markdown')
            return PRODUCT_INPUT
        elif query.data == "search_list":
            context.user_data['search_type'] = query.data
            text = "📋 **Lista de Productos**\n\nEscribe los productos separados por comas o saltos de línea:\n\n*Ejemplos:*\n• `aceite vegetal, pan tajado, sal`\n• `aceite vegetal`\n  `pan tajado`\n  `sal`"
            await query.edit_message_text(text, parse_mode='Markdown')
            return PRODUCT_INPUT
        elif query.data == "search_compare":
            context.user_data['search_type'] = query.data
            text = "🏪 **Comparar Tiendas**\n\nEscribe el producto para comparar precios en todas las tiendas:"
            await query.edit_message_text(text, parse_mode='Markdown')
            return PRODUCT_INPUT
        
        # Callbacks existentes
        elif query.data == "back_main":
            return await self.back_to_main(update, context)
        elif query.data == "new_search":
            return await self.start_price_search(update, context)
        elif query.data == "new_recipe":
            return await self.start_recipe_analysis(update, context)
        elif query.data.startswith("newsletter_"):
            return await self.handle_newsletter_config(update, context)
        elif query.data.startswith("discount_"):
            return await self.handle_discount_store_selection(update, context)
        elif query.data.startswith("store_"):
            store = query.data.replace("store_", "")
            return await self.execute_search(update, context, store)
        elif query.data in ["save_recipe", "create_shopping_list"]:
            await query.edit_message_text(
                f"✅ {query.data.replace('_', ' ').title()} - Funcionalidad en desarrollo",
                parse_mode='Markdown'
            )
            return BotState.MAIN_MENU.value
        else:
            # Callback query no manejada
            logger.warning(f"Callback no manejado: {query.data}")
            return BotState.MAIN_MENU.value

    async def handle_newsletter_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Maneja la configuración del newsletter"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        if query.data == "newsletter_on":
            self.user_data[user_id]['newsletter_enabled'] = True
            text = "✅ Newsletter activado. Recibirás descuentos cada día a las 7:00 AM"
        elif query.data == "newsletter_off":
            self.user_data[user_id]['newsletter_enabled'] = False
            text = "❌ Newsletter desactivado"
        else:
            text = "⚙️ Configuración en desarrollo"
        
        await query.edit_message_text(text)
        return BotState.MAIN_MENU.value

    async def back_to_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Vuelve al menú principal"""
        # Limpiar datos temporales
        context.user_data.clear()
        
        # Simplemente retornar al estado principal
        return BotState.MAIN_MENU.value

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancela la operación actual"""
        await update.message.reply_text(
            "❌ Operación cancelada. Usa /start para volver al menú principal."
        )
        return ConversationHandler.END

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja errores del bot"""
        logger.error(f"Error: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Ocurrió un error. Usa /start para reiniciar."
            )
    
    def _get_scraper_manager(self):
        """Obtiene el ScraperManager, creándolo si es necesario"""
        if self.scraper_manager is None:
            logger.info("Inicializando ScraperManager...")
            self.scraper_manager = ScraperManager(max_workers=3)
        return self.scraper_manager
    
    def cleanup(self):
        """Limpia recursos del bot"""
        try:
            if self.scraper_manager:
                self.scraper_manager.close()
                logger.info("Bot limpiado correctamente")
        except Exception as e:
            logger.error(f"Error en limpieza del bot: {e}")

    def register_handlers(self, application: Application) -> None:
        """Registra todos los handlers del bot en la aplicación"""
        # Crear manejador de conversación principal
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                BotState.MAIN_MENU.value: [
                    # Estrategia 1: Patrones exactos con VS-16 opcional
                    MessageHandler(filters.Regex(r"^🔍\ufe0f?\s*Buscar Precios$"), self.start_price_search),
                    MessageHandler(filters.Regex(r"^📢\ufe0f?\s*Descuentos$"), self.start_discount_search),
                    MessageHandler(filters.Regex(r"^👨‍🍳\ufe0f?\s*Analizar Receta$"), self.start_recipe_analysis),
                    MessageHandler(filters.Regex(r"^📰\ufe0f?\s*Newsletter$"), self.configure_newsletter),
                    MessageHandler(filters.Regex(r"^🧁\ufe0f?\s*Órdenes Pastelería$"), self.start_bakery_orders),
                    MessageHandler(filters.Regex(r"^⚙️\ufe0f?\s*Configuración$"), self.show_settings),
                    MessageHandler(filters.Regex(r"^❓\ufe0f?\s*Ayuda$"), self.show_help),
                    
                    # Estrategia 2: Patrones sin emoji como respaldo
                    MessageHandler(filters.Regex(r"^Buscar Precios$"), self.start_price_search),
                    MessageHandler(filters.Regex(r"^Descuentos$"), self.start_discount_search),
                    MessageHandler(filters.Regex(r"^Analizar Receta$"), self.start_recipe_analysis),
                    MessageHandler(filters.Regex(r"^Newsletter$"), self.configure_newsletter),
                    MessageHandler(filters.Regex(r"^Órdenes Pastelería$"), self.start_bakery_orders),
                    MessageHandler(filters.Regex(r"^Configuración$"), self.show_settings),
                    MessageHandler(filters.Regex(r"^Ayuda$"), self.show_help),
                    
                    # Callback queries (inline keyboard) - PRINCIPAL
                    CallbackQueryHandler(self.handle_callback_query),
                    
                    # Estrategia 3: Handler universal como último recurso
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.universal_message_handler)
                ],
                PRODUCT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_product_input)],
                STORE_SELECTION: [CallbackQueryHandler(self.handle_store_selection)],
                RECIPE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_recipe_name)],
                INGREDIENT_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_ingredient_list)],
                BotState.DISCOUNT_SEARCH.value: [CallbackQueryHandler(self.handle_discount_store_selection)],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CommandHandler("start", self.start),  # Permite reiniciar en cualquier momento
                MessageHandler(filters.TEXT, self.universal_message_handler)  # Captura todo
            ],
            per_chat=True,
            per_user=True,
            allow_reentry=True,
        )
        
        # Agregar manejadores
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("help", self.show_help))
        application.add_handler(CommandHandler("debug", self.test_patterns))
        application.add_handler(CommandHandler("test", self.test_patterns))
        application.add_handler(CommandHandler("stats", self.show_warehouse_stats))
        application.add_handler(CommandHandler("warehouse", self.query_warehouse))
        
        # Handler global para callback queries (fuera del ConversationHandler)
        application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # Manejador de errores
        application.add_error_handler(self.error_handler)
        
        logger.info("Handlers registrados correctamente")

def main() -> None:
    """Función principal del bot con debugging avanzado"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN no está configurado")
        return
    
    # Crear instancia del bot
    bot = ShoppingBot()
    
    # Crear aplicación
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Configurar manejador de conversación principal con múltiples estrategias
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", bot.start)],
        states={
            BotState.MAIN_MENU.value: [
                # Estrategia 1: Patrones exactos con VS-16 opcional
                MessageHandler(filters.Regex(r"^🔍\ufe0f?\s*Buscar Precios$"), bot.start_price_search),
                MessageHandler(filters.Regex(r"^📢\ufe0f?\s*Descuentos$"), bot.start_discount_search),
                MessageHandler(filters.Regex(r"^👨‍🍳\ufe0f?\s*Analizar Receta$"), bot.start_recipe_analysis),
                MessageHandler(filters.Regex(r"^📰\ufe0f?\s*Newsletter$"), bot.configure_newsletter),
                MessageHandler(filters.Regex(r"^🧁\ufe0f?\s*Órdenes Pastelería$"), bot.start_bakery_orders),
                MessageHandler(filters.Regex(r"^⚙️\ufe0f?\s*Configuración$"), bot.show_settings),
                MessageHandler(filters.Regex(r"^❓\ufe0f?\s*Ayuda$"), bot.show_help),
                
                # Estrategia 2: Patrones sin emoji como respaldo
                MessageHandler(filters.Regex(r"^Buscar Precios$"), bot.start_price_search),
                MessageHandler(filters.Regex(r"^Descuentos$"), bot.start_discount_search),
                MessageHandler(filters.Regex(r"^Analizar Receta$"), bot.start_recipe_analysis),
                MessageHandler(filters.Regex(r"^Newsletter$"), bot.configure_newsletter),
                MessageHandler(filters.Regex(r"^Órdenes Pastelería$"), bot.start_bakery_orders),
                MessageHandler(filters.Regex(r"^Configuración$"), bot.show_settings),
                MessageHandler(filters.Regex(r"^Ayuda$"), bot.show_help),
                
                # Callback queries (inline keyboard) - PRINCIPAL
                CallbackQueryHandler(bot.handle_callback_query),
                
                # Estrategia 3: Handler universal como último recurso
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.universal_message_handler)
            ],
            PRODUCT_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_product_input)],
            STORE_SELECTION: [CallbackQueryHandler(bot.handle_store_selection)],
            RECIPE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_recipe_name)],
            INGREDIENT_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_ingredient_list)],
            BotState.DISCOUNT_SEARCH.value: [CallbackQueryHandler(bot.handle_discount_store_selection)],
        },
        fallbacks=[
            CommandHandler("cancel", bot.cancel),
            CommandHandler("start", bot.start), # Permite reiniciar en cualquier momento
            MessageHandler(filters.TEXT, bot.universal_message_handler) # Captura todo
        ],
        per_chat=True,
        per_user=True,
        allow_reentry=True,
    )
    
    # Agregar manejadores adicionales
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", bot.show_help))
    application.add_handler(CommandHandler("debug", bot.test_patterns))
    application.add_handler(CommandHandler("test", bot.test_patterns))
    application.add_handler(CommandHandler("stats", bot.show_warehouse_stats))
    application.add_handler(CommandHandler("warehouse", bot.query_warehouse))
    
    # Handler global para callback queries (fuera del ConversationHandler)
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
    
    application.add_error_handler(bot.error_handler)
    
    # Ejecutar bot
    logger.info("🤖 Bot iniciado - Asistente de Compras")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario")
    finally:
        bot.cleanup()

if __name__ == "__main__":
    main()