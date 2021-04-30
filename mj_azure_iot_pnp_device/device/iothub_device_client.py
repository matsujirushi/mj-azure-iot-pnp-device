import logging
import json
from ..contents import *
from azure.iot.device import Message
from azure.iot.device import MethodResponse

logger = logging.getLogger(__name__)


class IoTHubDeviceClient:
    def set_iot_hub_device_client(self, client):
        self.__iot_hub_device_client = client

    async def connect(self):
        # Connect the Azure IoT Hub
        await self.__iot_hub_device_client.connect()

        # Processing Device Twin document
        twin = await self.__iot_hub_device_client.get_twin()
        await self.__twin_document_handler(twin)

        # Attach Device Twin patch handler
        self.__iot_hub_device_client.on_twin_desired_properties_patch_received = self.__twin_patch_handler
        # Attach Direct Method handler
        self.__iot_hub_device_client.on_method_request_received = self.__direct_method_handler

    async def disconnect(self):
        # Disconnect the Azure IoT Hub
        await self.__iot_hub_device_client.disconnect()

    async def send_telemetry(self, name):
        payload = {}

        if isinstance(name, str):
            payload[name] = getattr(self, name).value
        elif isinstance(name, tuple):
            for n in name:
                payload[n] = getattr(self, n).value
        else:
            raise RuntimeError()

        msg = Message(json.dumps(payload))
        msg.content_encoding = "utf-8"
        msg.content_type = "application/json"
        await self.__iot_hub_device_client.send_message(msg)

    async def __send_readonly_property(self, name, value):
        await self.__iot_hub_device_client.patch_twin_reported_properties({name: value})

    async def __send_writable_property_confirm(self, name, value, ack_code, ack_version, description="Completed"):
        prop_dict = {}
        prop_dict[name] = {
            "value": value,
            "ac": ack_code,
            "av": ack_version,
            "ad": description,
        }

        await self.__iot_hub_device_client.patch_twin_reported_properties(prop_dict)

    async def __twin_document_handler(self, twin):
        logger.info(f"[twin] Received twin = {twin}")

        if "$version" not in twin["desired"]:
            raise RuntimeError()

        for name in self.__dict__:
            content = getattr(self, name)

            if isinstance(content, Telemetry):
                pass

            elif isinstance(content, ReadOnlyProperty):
                send_reported = False
                if name in twin["reported"]:
                    if twin["reported"][name] != content.value:
                        send_reported = True
                else:
                    send_reported = True

                if send_reported:
                    logger.info(f"[twin] Send ReadOnlyProperty {name} = {content.value}")
                    await self.__send_readonly_property(name, content.value)

            elif isinstance(content, WritableProperty):
                if name in twin["desired"]:
                    version = twin["desired"]["$version"]
                    content.value = twin["desired"][name]
                    logger.info(f"[twin] Received WritableProperty {name} = {content.value}")
                else:
                    version = 1

                logger.info(f"[twin] Send WritableProperty {name} = {content.value}")
                await self.__send_writable_property_confirm(name, content.value, 200, version)

            elif isinstance(content, Command):
                pass

    async def __twin_patch_handler(self, patch):
        logger.info(f"[patch] Received patch = {patch}")

        ack_code = 200

        for name in patch.keys():
            if name == '$version':
                continue

            logger.info(f"[patch] Receive WritableProperty {name} = {patch[name]}")

            ack_code = 400

            if name in self.__dict__:
                content = getattr(self, name)

                if isinstance(content, WritableProperty):
                    content.value = patch[name]
                    ack_code = 200

            await self.__send_writable_property_confirm(name, patch[name], ack_code, patch["$version"])

    async def __direct_method_handler(self, command_request):
        name = command_request.name
        payload = command_request.payload

        logger.info(f"[command] Received request = {name}, payload={payload}")

        response_status = 400
        response_payload = None

        if name in self.__dict__:
            content = getattr(self, name)
            if content.handler is not None:
                response_status, response_payload = content.handler(payload)

        command_response = MethodResponse.create_from_method_request(command_request, response_status, response_payload)
        await self.__iot_hub_device_client.send_method_response(command_response)
