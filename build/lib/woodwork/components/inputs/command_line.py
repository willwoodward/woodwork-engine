from threading import Thread

from components.inputs.inputs import inputs

class command_line(inputs):
    def __init__(self, name, config):
        print("Creating command line input...")
        
        super().__init__(name)
        
        if config["to"]:
            self.destination = config["to"]

        print("Command line input initialised, type \";\" to exit. Begin typing:")
        
        thread = Thread(target=self.__input_loop)
        thread.start()
        thread.join()     
    
    def __input_loop(self):
        while True:
            x = input()
            
            if x == "exit" or x == ";":
                break
            
            # Send the input to the component
            print(self.destination.input_handler(x))
