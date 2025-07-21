#!/usr/bin/env python3
"""
Prueba estricta para verificar que el agente use SOLO datos reales de la base de datos
"""

import asyncio
import logging
import re

# Configurar logging
logging.basicConfig(level=logging.INFO)

async def test_strict_menu_accuracy():
    """
    Prueba estricta que compara datos reales con respuesta del agente
    """
    try:
        from app.core.smart_graph import smart_process_message
        from app.core.tools import get_menu
        
        print("="*70)
        print("PRUEBA ESTRICTA: VERIFICACIÓN DE DATOS REALES VS RESPUESTA")
        print("="*70)
        
        # 1. Obtener datos reales de la base de datos
        print("\n📊 OBTENIENDO DATOS REALES DE LA BASE DE DATOS...")
        real_menu_data = await get_menu.ainvoke({})
        
        # Procesar datos reales
        real_products = {}
        for item in real_menu_data:
            name = item.get('name', '').lower()
            price = float(item.get('price', 0))
            size = item.get('options', {}).get('size', 'sin tamaño').lower()
            category = item.get('category', '').lower()
            
            if name not in real_products:
                real_products[name] = []
            real_products[name].append({
                'price': price,
                'size': size,
                'category': category
            })
        
        print(f"✅ Datos reales cargados: {len(real_products)} productos únicos")
        
        # 2. Obtener respuesta del agente
        print("\n🤖 OBTENIENDO RESPUESTA DEL AGENTE...")
        agent_response = await smart_process_message('test_strict_user', 'Qué pizzas tienen disponibles con sus precios?')
        
        print(f"📝 RESPUESTA DEL AGENTE:")
        print(f"   {agent_response}")
        
        # 3. Analizar la respuesta del agente
        print("\n🔍 ANALIZANDO EXACTITUD DE LA RESPUESTA...")
        
        # Extraer productos y precios mencionados por el agente
        response_lower = agent_response.lower()
        
        # Buscar patrones de productos y precios
        price_pattern = r'\$(\d+\.?\d*)'
        product_pattern = r'([a-záéíóúñ\s]+).*?\$(\d+\.?\d*)'
        
        agent_prices = re.findall(price_pattern, response_lower)
        agent_products = []
        
        # Buscar productos específicos conocidos
        known_products = list(real_products.keys())
        for product in known_products:
            if product in response_lower:
                agent_products.append(product)
        
        print(f"📊 PRODUCTOS MENCIONADOS POR EL AGENTE: {agent_products}")
        print(f"📊 PRECIOS MENCIONADOS POR EL AGENTE: {agent_prices}")
        
        # 4. Verificación de exactitud
        errors = []
        warnings = []
        
        # Verificar productos inventados
        for product in agent_products:
            if product not in real_products:
                errors.append(f"Producto INVENTADO: '{product}' no existe en la base de datos")
        
        # Verificar precios
        mentioned_prices = [float(p) for p in agent_prices]
        real_prices = []
        for product_data in real_products.values():
            for variant in product_data:
                real_prices.append(variant['price'])
        
        for price in mentioned_prices:
            if price not in real_prices:
                errors.append(f"Precio INVENTADO: ${price} no existe en la base de datos")
        
        # Buscar palabras sospechosas que podrían indicar productos inventados
        suspicious_words = ['carnitas', 'pizza de la casa', 'hawaiana', 'especial', 'suprema']
        for word in suspicious_words:
            if word in response_lower:
                # Verificar si es un producto real
                if word not in real_products:
                    warnings.append(f"Palabra sospechosa encontrada: '{word}' - verificar si es un producto real")
        
        # 5. Reporte final
        print("\n" + "="*70)
        print("📋 REPORTE DE EXACTITUD:")
        print("="*70)
        
        if not errors and not warnings:
            print("✅ PERFECTO: El agente usa SOLO datos reales de la base de datos")
            return True
        
        if errors:
            print("❌ ERRORES CRÍTICOS ENCONTRADOS:")
            for error in errors:
                print(f"   • {error}")
        
        if warnings:
            print("⚠️ ADVERTENCIAS:")
            for warning in warnings:
                print(f"   • {warning}")
        
        return len(errors) == 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_switching():
    """
    Demostrar cómo cambiar entre LLMs
    """
    print("\n" + "="*70)
    print("🔄 DEMOSTRACIÓN DE CAMBIO DE LLM")
    print("="*70)
    
    try:
        from app.llm_factory import get_available_models, switch_llm, test_current_llm
        
        print("📋 MODELOS DISPONIBLES:")
        models = get_available_models()
        for provider, config in models.items():
            print(f"\n{provider.upper()}:")
            for model_name in config['models'].keys():
                print(f"  • {model_name}")
        
        print(f"\n🔧 PARA CAMBIAR LLM:")
        print(f"   1. Configura variables de entorno:")
        print(f"      export LLM_PROVIDER=openai")
        print(f"      export LLM_MODEL=gpt-4o-mini")
        print(f"      export OPENAI_API_KEY=tu_api_key")
        print(f"   2. Reinicia la aplicación")
        
        print(f"\n🧪 PROBANDO LLM ACTUAL:")
        if test_current_llm():
            print("✅ LLM actual funciona correctamente")
        else:
            print("❌ LLM actual tiene problemas")
            
    except Exception as e:
        print(f"❌ Error en demostración de LLM: {e}")

if __name__ == "__main__":
    print("Ejecutando pruebas de exactitud...")
    
    # Prueba de exactitud
    success = asyncio.run(test_strict_menu_accuracy())
    
    # Demostración de cambio de LLM
    asyncio.run(test_llm_switching())
    
    if success:
        print("\n🎉 PRUEBA PASADA - EL AGENTE USA DATOS REALES")
    else:
        print("\n🚨 PRUEBA FALLIDA - EL AGENTE SIGUE INVENTANDO DATOS")
        exit(1) 