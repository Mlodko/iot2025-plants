import aiomqtt
import asyncio

async def main():
    print("Starting MQTT listener...")
    print("Stop with Ctrl+C")
    try:
        async with aiomqtt.Client(hostname="localhost", port=1883) as client:
            _ = await client.subscribe('test')
            async for message in client.messages:
                try:
                    # Handle different payload types
                    if isinstance(message.payload, bytes):
                        payload_str = message.payload.decode('utf-8')
                    else:
                        payload_str = str(message.payload)
                    
                    print(f"Received message on topic '{message.topic}': {payload_str}")
                except Exception as decode_error:
                    print(f"Error decoding message: {decode_error}")              
    except Exception as e:
        print(f"Connection error: {e}")
        
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping MQTT listener...")
        