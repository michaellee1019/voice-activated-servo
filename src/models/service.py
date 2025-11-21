import asyncio
from typing import ClassVar, Dict, List, Mapping, Optional, Sequence, Tuple

from typing_extensions import Self
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.services.generic import *
from viam.utils import ValueTypes
from viam.components.servo import Servo
from speech_service_api import SpeechService


class Service(Generic, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(
        ModelFamily("michaellee1019", "voice-activated-servo"), "service"
    )
    speech_service: SpeechService
    servo: Servo
    commands: Dict[str, List[int]]

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        """This method creates a new instance of this Generic service.
        The default implementation sets the name from the `config` parameter and then calls `reconfigure`.

        Args:
            config (ComponentConfig): The configuration for this resource
            dependencies (Mapping[ResourceName, ResourceBase]): The dependencies (both required and optional)

        Returns:
            Self: The resource
        """
        return super().new(config, dependencies)

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """This method allows you to validate the configuration object received from the machine,
        as well as to return any required dependencies or optional dependencies based on that `config`.

        Args:
            config (ComponentConfig): The configuration for this resource

        Returns:
            Tuple[Sequence[str], Sequence[str]]: A tuple where the
                first element is a list of required dependencies and the
                second element is a list of optional dependencies
        """
        if "speech_service" not in config.attributes.fields:
            raise ValueError("speech_service is required")
        if "servo" not in config.attributes.fields:
            raise ValueError("servo is required")
        if "commands" not in config.attributes.fields:
            raise ValueError("commands is required")
        
        # Get the speech_service and servo names
        speech_service_name = config.attributes.fields["speech_service"].string_value
        servo_name = config.attributes.fields["servo"].string_value
        
        # Validate commands structure
        commands = config.attributes.fields["commands"].struct_value
        
        for phrase, angles_value in commands.fields.items():
            if not isinstance(phrase, str):
                raise ValueError("command phrase must be a string")
            
            # Get the list value
            angles_list = angles_value.list_value.values
            
            if not angles_list:
                raise ValueError(f"command angles for '{phrase}' cannot be empty")
            
            for angle_value in angles_list:
                angle = angle_value.number_value
                if not (0 <= angle <= 180):
                    raise ValueError(f"command angles for '{phrase}' must be integers between 0 and 180")
        
        # Return speech_service and servo as required dependencies
        return [speech_service_name, servo_name], []

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        """This method allows you to dynamically update your service when it receives a new `config` object.

        Args:
            config (ComponentConfig): The new configuration
            dependencies (Mapping[ResourceName, ResourceBase]): Any dependencies (both required and optional)
        """
        self.logger.debug("reconfiguring...")
        
        # Get speech_service and servo names
        speech_service_name = config.attributes.fields["speech_service"].string_value
        servo_name = config.attributes.fields["servo"].string_value
        
        # Get dependencies
        for resource_name, resource in dependencies.items():
            if resource_name.name == speech_service_name:
                self.speech_service = resource
                self.logger.info(f"Found speech service: {speech_service_name}")
            if resource_name.name == servo_name:
                self.servo = resource
                self.logger.info(f"Found servo: {servo_name}")
        
        # Parse commands
        self.commands = {}
        commands_struct = config.attributes.fields["commands"].struct_value
        
        for phrase, angles_value in commands_struct.fields.items():
            angles = []
            for angle_value in angles_value.list_value.values:
                angles.append(int(angle_value.number_value))
            self.commands[phrase] = angles
        
        self.logger.info(f"Configured commands: {list(self.commands.keys())}")
        self.logger.debug("reconfigured")
        
        return super().reconfigure(config, dependencies)

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        
        if command.get("listen_for_command"):
            # Get commands from the speech service queue
            # The get_commands method returns a list of strings from the command buffer
            commands_from_queue = await self.speech_service.get_commands(number=1)
            
            if not commands_from_queue or len(commands_from_queue) == 0:
                return {"status": "no voice command heard"}
            
            heard_text = commands_from_queue[0]
            
            if heard_text in [None, ""]:
                return {"status": "no voice command heard"}
            else: 
                commands_heard = []
                for phrase in self.commands.keys():
                    if phrase.lower() in heard_text.lower():
                        angles = self.commands[phrase]
                        for angle in angles:
                            await self.servo.move(angle)
                            await asyncio.sleep(1)
                            self.logger.debug(f"Moving servo to angle {angle} for command {phrase}")
                        commands_heard.append(phrase)
                if len(commands_heard) > 0:
                    return {"status": "voice commands heard", "voice_commands": commands_heard, "heard": heard_text}
                else:
                    return {"status": "no voice commands heard", "heard": heard_text}

