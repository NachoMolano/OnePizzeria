#!/usr/bin/env python3
"""
Prueba para verificar el procesamiento dinámico del menú.
Verifica que el agente use datos reales de la base de datos y responda
preguntas del menú sin pedir información personal innecesariamente.
"""

import asyncio
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)

async def test_simple_menu_questions():
    """
    Prueba simple de preguntas del menú
    """
    try:
        from app.core.smart_graph import smart_process_message
        
        print("="*60)
        print("PRUEBA SIMPLE: PREGUNTAS DEL MENÚ")
        print("="*60)
        
        # Test 1: Pregunta directa sobre pizzas
        print("\n🍕 PREGUNTA: ¿Qué pizzas tienen?")
        response1 = await smart_process_message('test_simple_menu', 'Qué pizzas tienen?')
        print(f"📝 RESPUESTA: {response1}")
        
        # Test 2: Pregunta sobre precio específico
        print("\n💰 PREGUNTA: ¿Cuánto cuesta la Margherita?")
        response2 = await smart_process_message('test_simple_menu', 'Cuánto cuesta la Margherita?')
        print(f"📝 RESPUESTA: {response2}")
        
        # Análisis simple
        print("\n" + "="*60)
        print("🔍 ANÁLISIS RÁPIDO:")
        print("="*60)
        
        # Verificar si responde sobre el menú
        if "margherita" in response1.lower() or "pepperoni" in response1.lower():
            print("✅ TEST 1: El agente menciona pizzas específicas")
        else:
            print("❌ TEST 1: El agente no menciona pizzas específicas")
            
        if "precio" in response2.lower() or "$" in response2 or "cuesta" in response2.lower():
            print("✅ TEST 2: El agente menciona precios")
        else:
            print("❌ TEST 2: El agente no menciona precios")
            
        # Verificar si pide información personal innecesariamente
        if "nombre" in response1.lower() or "nombre" in response2.lower():
            print("⚠️ ADVERTENCIA: El agente pide información personal para consultas del menú")
        else:
            print("✅ BIEN: El agente no pide información personal para consultas del menú")
        
        print("\n🎯 CONCLUSIÓN: Revisa las respuestas arriba para evaluar la mejora")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_menu_questions()) 