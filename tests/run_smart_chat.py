#!/usr/bin/env python3
"""
🍕 SMART CHAT INTERFACE - Pizzería Chatbot con Memoria Inteligente
Interfaz interactiva mejorada que demuestra las capacidades del nuevo sistema de memoria.
"""

import asyncio
import uuid
import sys
import os
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.smart_graph import smart_process_message
from app.core.smart_memory import smart_memory


def print_header():
    """Print a beautiful header for the chat session."""
    print("🍕" + "=" * 60 + "🍕")
    print("       PIZZERIA CHATBOT - SMART MEMORY SYSTEM")
    print("🧠" + "=" * 60 + "🧠")
    print()
    print("✨ NUEVAS CARACTERÍSTICAS:")
    print("   • 🧠 Memoria conversacional inteligente")
    print("   • 💾 Recuerda conversaciones entre sesiones")
    print("   • 🎯 Contexto personalizado por usuario")
    print("   • 🔄 Ventana deslizante de mensajes")
    print()
    print("💬 Empieza a conversar con el bot")
    print("🚪 Comandos disponibles:")
    print("   • 'exit' - Terminar sesión")
    print("   • 'stats' - Ver estadísticas de memoria")
    print("   • 'new' - Simular nuevo usuario")
    print("   • 'clear' - Limpiar cache de memoria")
    print()


def print_user_info(user_id: str):
    """Print user information."""
    print(f"👤 Tu ID de usuario: {user_id}")
    print("-" * 60)


async def show_memory_stats(user_id: str):
    """Show memory statistics for the current user."""
    try:
        stats = await smart_memory.get_conversation_stats(user_id)
        
        print("\n📊 ESTADÍSTICAS DE MEMORIA:")
        print(f"   • Mensajes almacenados: {stats['message_count']}")
        print(f"   • Contexto del cliente: {len(stats['customer_context_keys'])} campos")
        print(f"   • Última actividad: {stats['last_activity'][:19]}")
        print(f"   • Cache hit: {'✅' if stats['cache_hit'] else '❌'}")
        
        if stats['customer_context_keys']:
            print(f"   • Datos guardados: {', '.join(stats['customer_context_keys'])}")
        
        print()
        
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")


async def process_special_commands(user_input: str, current_user_id: str) -> tuple[bool, str]:
    """
    Process special commands that don't go to the bot.
    Returns (should_continue, new_user_id)
    """
    command = user_input.lower().strip()
    
    if command in ["exit", "quit", "salir"]:
        print("\n🍕 ¡Gracias por visitarnos! ¡Hasta pronto!")
        return False, current_user_id
    
    elif command == "stats":
        await show_memory_stats(current_user_id)
        return True, current_user_id
    
    elif command == "new":
        new_user_id = f"smart_user_{uuid.uuid4().hex[:8]}"
        print(f"\n🆕 Simulando nuevo usuario: {new_user_id}")
        print_user_info(new_user_id)
        return True, new_user_id
    
    elif command == "clear":
        smart_memory.clear_cache()
        print("\n🧹 Cache de memoria limpiado")
        return True, current_user_id
    
    elif command == "help":
        print("\n📖 COMANDOS DISPONIBLES:")
        print("   • 'exit' - Terminar sesión")
        print("   • 'stats' - Ver estadísticas de memoria")
        print("   • 'new' - Simular nuevo usuario")
        print("   • 'clear' - Limpiar cache de memoria")
        print("   • 'help' - Mostrar esta ayuda")
        return True, current_user_id
    
    # Not a special command
    return True, current_user_id


async def main():
    """
    Main function to run the interactive smart chat interface.
    """
    print_header()
    
    # Generate a unique user_id for each test run
    user_id = f"smart_user_{uuid.uuid4().hex[:8]}"
    print_user_info(user_id)

    message_count = 0

    while True:
        try:
            # Get user input
            user_input = input("\n👤 Tú: ").strip()
            
            # Skip empty input
            if not user_input:
                continue
            
            # Process special commands
            should_continue, user_id = await process_special_commands(user_input, user_id)
            if not should_continue:
                break
            
            # If it's a special command that was processed, continue to next iteration
            if user_input.lower().strip() in ["stats", "new", "clear", "help"]:
                continue
            
            # Process the message using our smart memory system
            print("🤖 Bot: ", end="", flush=True)
            
            # Show thinking indicator with message count
            message_count += 1
            print(f"🧠 Pensando (msg #{message_count})...", end="", flush=True)
            
            start_time = datetime.now()
            
            # Get response from our smart memory system
            response = await smart_process_message(user_id, user_input)
            
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()
            
            # Clear the thinking indicator and show response
            print(f"\r🤖 Bot: {response}")
            print(f"⏱️  Tiempo de respuesta: {response_time:.2f}s")
            
        except KeyboardInterrupt:
            print("\n\n🍕 ¡Gracias por visitarnos! ¡Hasta pronto!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("💡 Tip: Intenta de nuevo o escribe 'exit' para terminar")


async def quick_system_test():
    """
    Quick test function to verify the smart memory system is working.
    """
    print("🧪 Probando sistema de memoria inteligente...")
    test_user = f"test_{uuid.uuid4().hex[:6]}"
    
    try:
        # Test 1: First message
        response1 = await smart_process_message(test_user, "Hola")
        print(f"✅ Test 1 - Primer mensaje: OK")
        
        # Test 2: Memory persistence
        response2 = await smart_process_message(test_user, "Mi nombre es Test User")
        print(f"✅ Test 2 - Información guardada: OK")
        
        # Test 3: Memory recall
        response3 = await smart_process_message(test_user, "¿Cuál es mi nombre?")
        print(f"✅ Test 3 - Memoria funcional: OK")
        
        # Test 4: Statistics
        stats = await smart_memory.get_conversation_stats(test_user)
        if stats['message_count'] >= 6:  # 3 human + 3 bot messages
            print(f"✅ Test 4 - Estadísticas: OK ({stats['message_count']} mensajes)")
        else:
            print(f"⚠️  Test 4 - Estadísticas: {stats['message_count']} mensajes (esperados: 6)")
        
        print("🎉 Sistema funcionando correctamente!")
        return True
        
    except Exception as e:
        print(f"❌ Test falló: {e}")
        return False


async def demo_conversation_memory():
    """
    Demonstrate conversation memory capabilities.
    """
    print("\n🎭 DEMOSTRACIÓN DE MEMORIA CONVERSACIONAL:")
    print("-" * 50)
    
    demo_user = f"demo_{uuid.uuid4().hex[:6]}"
    
    demo_messages = [
        "Hola",
        "Mi nombre es María García",
        "Mi teléfono es 300-123-4567",
        "¿Qué pizzas tienen?",
        "Quiero una pizza hawaiana mediana"
    ]
    
    for i, message in enumerate(demo_messages, 1):
        print(f"\n{i}. 👤 Demo: {message}")
        response = await smart_process_message(demo_user, message)
        print(f"   🤖 Bot: {response[:100]}...")
        
        # Show memory stats after each message
        stats = await smart_memory.get_conversation_stats(demo_user)
        print(f"   📊 Memoria: {stats['message_count']} mensajes")
    
    print(f"\n✨ El bot ahora recuerda toda la conversación de María García!")
    print("💡 En una sesión real, esta memoria persistiría entre desconexiones.")


if __name__ == "__main__":
    try:
        print("🚀 Iniciando Pizzería Chatbot con Memoria Inteligente...")
        print("🔧 Verificando sistema...")
        
        # Quick system test
        if asyncio.run(quick_system_test()):
            print("✅ Sistema listo!\n")
            
            # Ask user what they want to do
            print("🎯 ¿Qué te gustaría hacer?")
            print("1. 💬 Chat interactivo")
            print("2. 🎭 Ver demostración de memoria")
            print("3. ❌ Salir")
            
            choice = input("\nElige una opción (1-3): ").strip()
            
            if choice == "1":
                print("\n🚀 Iniciando chat interactivo...")
                asyncio.run(main())
            elif choice == "2":
                asyncio.run(demo_conversation_memory())
                print("\n💬 ¿Quieres probar el chat interactivo ahora? (s/n)")
                if input().lower().startswith('s'):
                    asyncio.run(main())
            else:
                print("👋 ¡Hasta luego!")
        else:
            print("❌ Sistema no está listo. Verifica tu configuración:")
            print("   • poetry install")
            print("   • Variables de entorno en .env")
            print("   • Tabla smart_conversation_memory en Supabase")
            
    except KeyboardInterrupt:
        print("\n🍕 ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        print("💡 Asegúrate de que tu entorno esté configurado correctamente.") 