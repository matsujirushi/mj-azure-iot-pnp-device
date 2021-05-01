import asyncio
from datetime import timedelta, datetime
import os
import random
import sys
import time

from azure.iot.device.aio import IoTHubDeviceClient

from mj_azure_iot_pnp_device.device import IoTHubDeviceClient as MjClient
import mj_azure_iot_pnp_device.contents as MjCont
from varname import nameof

MODEL_ID = "dtmi:com:example:Thermostat;1"

#####################################################
# GLOBAL THERMOSTAT VARIABLES

max_temp = None
min_temp = None
avg_temp_list = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
moving_window_size = len(avg_temp_list)

#####################################################
# HANDLERS : User will define these handlers
# depending on what commands the DTMI defines


class GetMaxMinReportCommand(MjCont.Command):
    def handler(self, values):
        if values:
            print(
                "Will return the max, min and average temperature from the specified time {since} to the current time".format(
                    since=values
                )
            )
        print("Done generating")

        response_dict = {
            "maxTemp": max_temp,
            "minTemp": min_temp,
            "avgTemp": sum(avg_temp_list) / moving_window_size,
            "startTime": (datetime.utcnow() - timedelta(0, moving_window_size * 8)).isoformat() + "Z",
            "endTime": datetime.utcnow().isoformat() + "Z",
        }
        print(response_dict)
        return 200, response_dict

################################################
# Send telemetry


async def send_telemetry():
    print("Sending telemetry for temperature")
    global max_temp
    global min_temp
    current_avg_idx = 0

    while True:
        current_temp = random.randrange(10, 50)  # Current temperature in Celsius
        if not max_temp:
            max_temp = current_temp
        elif current_temp > max_temp:
            max_temp = current_temp

        if not min_temp:
            min_temp = current_temp
        elif current_temp < min_temp:
            min_temp = current_temp

        avg_temp_list[current_avg_idx] = current_temp
        current_avg_idx = (current_avg_idx + 1) % moving_window_size

        pnp_client.temperature.value = current_temp
        await pnp_client.send_telemetry(nameof(pnp_client.temperature))

        await asyncio.sleep(8)

#####################################################
# KEYBOARD INPUT LISTENER to quit application


def stdin_listener():
    while True:
        selection = input("Press Q to quit\n")
        if selection == "Q" or selection == "q":
            print("Quitting...")
            break

#####################################################
# PROVISION DEVICE


async def provision_device(provisioning_host, id_scope, registration_id, symmetric_key, model_id):
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=registration_id,
        id_scope=id_scope,
        symmetric_key=symmetric_key,
    )
    provisioning_device_client.provisioning_payload = {"modelId": MODEL_ID}
    return await provisioning_device_client.register()

#####################################################
# MAIN STARTS


async def main():
    global pnp_client

    # Create the device_client.
    switch = os.getenv("IOTHUB_DEVICE_SECURITY_TYPE")
    if switch == "DPS":
        provisioning_host = (
            os.getenv("IOTHUB_DEVICE_DPS_ENDPOINT")
            if os.getenv("IOTHUB_DEVICE_DPS_ENDPOINT")
            else "global.azure-devices-provisioning.net"
        )
        id_scope = os.getenv("IOTHUB_DEVICE_DPS_ID_SCOPE")
        registration_id = os.getenv("IOTHUB_DEVICE_DPS_DEVICE_ID")
        symmetric_key = os.getenv("IOTHUB_DEVICE_DPS_DEVICE_KEY")

        registration_result = await provision_device(
            provisioning_host, id_scope, registration_id, symmetric_key, model_id
        )

        if registration_result.status == "assigned":
            print("Device was assigned")
            print(registration_result.registration_state.assigned_hub)
            print(registration_result.registration_state.device_id)

            device_client = IoTHubDeviceClient.create_from_symmetric_key(
                symmetric_key=symmetric_key,
                hostname=registration_result.registration_state.assigned_hub,
                device_id=registration_result.registration_state.device_id,
                product_info=model_id,
            )
        else:
            raise RuntimeError(
                "Could not provision device. Aborting Plug and Play device connection."
            )

    elif switch == "connectionString":
        conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
        print("Connecting using Connection String " + conn_str)
        device_client = IoTHubDeviceClient.create_from_connection_string(
            conn_str, product_info=MODEL_ID
        )
    else:
        raise RuntimeError(
            "At least one choice needs to be made for complete functioning of this sample."
        )

    # Create the pnp client.
    pnp_client = MjClient()
    pnp_client.temperature = MjCont.Telemetry()
    #pnp_client.targetTemperature = MjCont.WritableProperty()
    pnp_client.maxTempSinceLastReboot = MjCont.ReadOnlyProperty()
    pnp_client.getMaxMinReport = GetMaxMinReportCommand()

    pnp_client.maxTempSinceLastReboot.value = 10.96

    # Connect the client.
    pnp_client.set_iot_hub_device_client(device_client)
    await pnp_client.connect()

    # Assign the send_telemetry task.
    send_telemetry_task = asyncio.create_task(send_telemetry())

    # Run the stdin listener in the event loop
    loop = asyncio.get_running_loop()
    user_finished = loop.run_in_executor(None, stdin_listener)
    await user_finished

    await device_client.disconnect()

    # Cleanup.
    send_telemetry_task.cancel()
    await device_client.shutdown()

    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
