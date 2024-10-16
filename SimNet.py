import random
import math
import json
import wsnsimpy.wsnsimpy_tk as wsp

TX_RANGE = 75
GATEWAY = 0  # Gateway id
INTERVAL = 10  # Increased to allow time for replies
DELAY = 1  # Delayed execution time
WEIGHT = 0.5  # Weight for calculating overhead (battery level and RSSI)
num_nodes = 25

###########################################################
def randdelay():
    '''
    Returns a random delay between 0.2 and 0.6 seconds.
    '''
    return random.uniform(0.2, 0.6)

###########################################################
class MyNode(wsp.LayeredNode):

    def init(self):
        '''
        Initialize the node.
        '''
        super().init()

        self.start_dreq = True
        self.last_request_time = 0  # Store the time when the request was sent
        self.tx_counter = 0
        self.neighbor_table = {}  # Dictionary to store neighbors, their overheads, and paths
        self.hop_count = 0 # Hop count to the gateway
        self.battery_level = 100
        self.rssi = 0
        self.apparent_battery = 100
        self.apparent_rssi = 0.0
        self.overhead = 0.0
        self.path = GATEWAY  # Path to the gateway
        self.clock_offset = 0  # Clock offset for synchronization
        self.start_flag = False
        self.data_cache = {}
        self.latency = 0

    def run(self):
        '''
        Main loop for Node.
        '''
        if self.id == GATEWAY:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the source node to blue
            self.scene.nodewidth(self.id, 2)

            #yield self.timeout(1)
            while True:
                self.log(f"STARTING")
                self.send_dreq()
                self.latency = self.now  # Store the time when the request was sent

                yield self.timeout(INTERVAL)

                yield self.timeout(10)
                self.scene.clearlinks()
                self.tx_counter += 1

    def send_dreq(self):
        '''
        Send a Data Request (DREQ) message to broadcast address.
        '''
        data = {
            'msg': 'dreq',
            'tx_counter': self.tx_counter,
            'battery_level': self.apparent_battery,
            'rssi': self.apparent_rssi,
            'overhead': self.overhead,
            'path': self.path,
            'clock': self.now
        }
        json_data = json.dumps(data).encode('utf-8')  # Encode data to JSON
        
        try:
            self.send(wsp.BROADCAST_ADDR, msg='dreq', data=json_data)
            #self.log(f"SENT: DREQ from {self.id}")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def send_dreply(self, src, data_cache):
        '''
        Send a Data Reply (DREP) message to the lowest overhead node.
        '''
        json_data = json.dumps(data_cache).encode('utf-8')  # Encode data to JSON

        self.start_flag = False

        try:
            self.send(self.path, msg='dreply', src=src, data=json_data)
            #self.log(f"SENT: DREP to {self.path}")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def on_receive(self, sender, msg, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''
        data = json.loads(kwargs['data'].decode('utf-8'))  # Load data from JSON

        if msg == 'dreq':

            self.is_new_transaction(data) # If new transaction, reset the node

            if not self.neighbor_table :            # First DREQ message received
                self.update_neighbor_table(sender, data) # Update the neighbor table
                self.overhead = self.calculate_overhead(sender, data) + data['overhead']  # Calculate node overhead
                if self.id != GATEWAY:
                    self.path = sender                      # Update self.path

                self.scene.addlink(sender, self.id, "parent") # Sim: Add a link between the sender and this node

                yield self.timeout(randdelay())
                self.send_dreq() # Forward the RREQ message to neighbors

                self.start_flag = True # Set the start flag to True
                self.start_reply()  # Start the reply process

            if self.neighbor_table:  # Node has received a DREQ message before
                if sender not in self.neighbor_table or data['overhead'] < self.neighbor_table[sender]['overhead']:

                    self.update_neighbor_table(sender, data) # Update the neighbor table

                    self.scene.addlink(sender, self.id, "parent") # Sim: Add a link between the sender and this node

                    # Check if the new recieved overhead is less than the current lowest overhead neighbor
                    if data['overhead'] < self.neighbor_table[self.lowest_overhead_neighbor()]['overhead']:
                        self.overhead = self.calculate_overhead(sender, data) + data['overhead']  # Update Node overhead
                        if self.id != GATEWAY:
                            self.path = sender                      # Update self.path

                        yield self.timeout(randdelay())
                        self.send_dreq()  # Forward the DREQ message

                        self.start_flag = False
                        yield self.timeout(DELAY)
                        self.start_flag = True
                        self.start_reply() # Start the reply process again


        elif msg == 'dreply':
            #self.log(f"RECIEVED: DREP from {sender}")

            # Incrmement hop count of recieved data
            # For all instances in the parsed data increment hop count by 1
            for value in data.values():
                value['hop_count'] += 1

            self.data_cache_update() # Add own data to the data_cache

            self.data_cache.update(data) # Add the sent data to the data_cache by merging dictionaries

            self.neighbor_table.setdefault(sender, {})['rx'] = 1 # Update neighbor packets received
            
            # Log the neighbor table entries where 'path' == self.id
            branches = {key: neighbor for key, neighbor in self.neighbor_table.items() if neighbor.get('path') == self.id}

            # Check if all branches have 'rx' == 1
            if all(neighbor.get('rx', 0) == 1 for neighbor in branches.values()):

                if self.id != GATEWAY: # If this node is not the gateway, forward the data packet
                    yield self.timeout(randdelay())             # Wait for a random delay
                    self.send_dreply(self.id, self.data_cache)   # Send the data packet to the next node

                else:                                                   # Data has reached the gateway                   
                    # self.log(f"RECEIVED data from connected nodes")
                    # self.log(f"\n" + self.init_data_cache())

                    self.log_data() # Log the data
                    self.log(f"DATA:\n" + self.init_data_cache())
                    self.log(f"COMPLETE")
                    for node in self.sim.nodes:
                        self.scene.nodecolor(node.id, 0, 0, 0)
                        self.scene.nodewidth(node.id, 1)
                    self.neighbor_table = {} # Reset the Gateway neighbor table


            else: 
                # Unrecieved branches
                pendingBranches = [key for key, neighbor in branches.items() if neighbor.get('rx', 0) == 0]
                #self.log(f"WAITING FOR: {pendingBranches}")

    def delayed_exec(self, delay, func, *args, **kwargs):
        '''Execute a function after a delay.'''
        return self.sim.delayed_exec(delay, func, *args, **kwargs)

    def start_reply(self):
        '''The reply process'''
        def start():
            if self.start_flag:
                # Check if edge node or reply timeout exceeded
                if self.is_edge_node():
                    # Set the color of the node to red
                    self.scene.nodecolor(self.id, 1, 0, 0)
                    self.scene.nodewidth(self.id, 2)

                    # Only add own data if not already added
                    if self.id not in self.data_cache:
                        self.data_cache_update()  # Add own data to the data cache
                    yield self.timeout(randdelay())
                    self.send_dreply(self.id, self.data_cache)  # Send the DREP message
        self.delayed_exec(DELAY, start)

    def calculate_overhead(self, sender, data):
        '''
        Calculate the overhead based on battery level and RSSI.
        '''
        #mac_bytes = bytes(int(b, 16) for b in sender_mac.split(':'))

        # Parse the battery and RSSI values as floats
        recieved_apparent_battery = float(data['battery_level'])
        recieved_apparent_rssi = float(data['rssi'])

        # Apparent normalized battery level and RSSI
        self.apparent_battery = self.read_battery_level() + recieved_apparent_battery
        self.apparent_rssi = self.read_rssi(sender) + recieved_apparent_rssi

        # Calculate and return the overhead
        overhead = round(WEIGHT * self.apparent_battery + (1 - WEIGHT) * -1*self.apparent_rssi,3)
        return overhead

    def is_new_transaction(self, data):
        '''If new transaction, reset the node.'''
        if data['tx_counter'] != self.tx_counter:
            self.tx_counter = data['tx_counter']
            self.neighbor_table = {}
            self.rssi = 0.0
            self.overhead = 0.0
            self.path = GATEWAY
            self.start_flag = False
            self.reply_flag = False  # Reset reply flag
            self.reply_deadline = None  # Reset the reply deadline
            self.data_cache = {}

    def is_edge_node(self):
        '''
        Determine if the node is an edge node by checking the path of all neighbors.
        The node is an edge node if its ID is not stored as the path in any neighbor's entry.
        Returns True if the node is an edge node, False otherwise.
        '''
        for neighbor in self.neighbor_table.values():
            if neighbor.get('path') == self.id:
                return False
        return True

    def lowest_overhead_neighbor(self):
        '''
        Returns the neighbor with the lowest overhead.
        '''
        return min(self.neighbor_table, key=lambda n: self.neighbor_table[n]['overhead'])

    def update_neighbor_table(self, sender, data):
        '''Update the neighbor table with sender info and add peer to ESP-NOW'''

        # mac_bytes = bytes(int(b, 16) for b in sender_mac.split(':'))

        # try:
        #     self.esp.add_peer(mac_bytes)  # Attempt to add the peer
        #     self.log(f"Added peer {sender_mac}")
        # except OSError as e:
        #     if e.args[0] == -12395:  # ESP_ERR_ESPNOW_EXIST
        #         pass  # Peer already exists, no action needed
        #     else:
        #         self.log(f"Error adding peer {sender_mac}: {e}")

        self.neighbor_table[sender] = {
            'battery_level': float(data['battery_level']),  # Store the battery level
            'rssi': float(data['rssi']),                   # Store the RSSI
            'overhead': float(data['overhead']),           # Store the overhead
            'path': data['path'],                          # Store the path
            'rx': 0                                        # Initialize packets received
        }

    def data_cache_update(self):
        '''
        Update the data cache with the collected data.
        '''

        # Random Sensor Data
        temperature, pressure, humidity = random.randint(20, 30), random.randint(1000, 1010), random.randint(40, 60)

        # Read actual battery level
        battery_level = self.read_battery_level()

        # Read RSSI value
        rssi = self.read_rssi(self.path)

        self.data_cache[str(self.id)] = {
            'time': self.now,
            'id': str(self.id),
            'pos': self.pos,
            'temperature': temperature,
            'humidity': humidity,
            'pressure': pressure,
            'rssi': rssi,
            'battery_level': battery_level,
            'hop_count': self.hop_count
        }

    def read_battery_level(self):
        '''
        Read the battery level from an ADC pin.
        '''
        return self.battery_level

    def read_rssi(self, sender):
        """
        Calculate the RSSI value based on distance using a path loss model.
        """
        # Get the sender node
        sender_node = self.sim.nodes[sender]

        # Calculate the distance between self and sender_node
        distance = math.hypot(
            self.pos[0] - sender_node.pos[0],
            self.pos[1] - sender_node.pos[1]
        )

        if distance == 0:
            # Avoid division by zero
            return 0.0

        # Use the calculated distance to compute RSSI
        self.rssi = -1 * round((distance / TX_RANGE) * 124, 1)
        return self.rssi

    def log(self, msg):
        print(f"Node {'#'+str(self.id):4}[{self.now:10.5f}] {msg}")

    def log_data(self):
        '''Log the collected data'''
        
        # Calculate latency in seconds
        self.latency = self.now - self.latency
        
        # Write latency to a CSV file
        latency_filename = 'latency_SIM.csv'
        try:
            if self.tx_counter == 0:
                # Overwrite the file if tx_counter is 0 and write header
                mode = 'w'
                data_string = "Tx,Latency\n"
                data_string += f"{self.tx_counter},{self.latency:.2f}\n"
            else:
                # Append to the file if tx_counter is not 0
                mode = 'a'
                data_string = f"{self.tx_counter},{self.latency:.2f}\n"
            
            with open(latency_filename, mode) as f:
                f.write(data_string)
            self.log(f"Latency data written to {latency_filename}")
        except Exception as e:
            self.log(f"Error writing latency data to file: {str(e)}")
        
        # Write data cache to CSV file
        data_filename = 'data_log_SIM.csv'
        try:
            if self.tx_counter == 0:
                # Overwrite the file if tx_counter is 0
                mode = 'w'
                data_string = self.init_csv_data_cache()
            else:
                # Append to the file if tx_counter is not 0
                mode = 'a'
                data_string = self.format_csv_data_cache()
            
            with open(data_filename, mode) as f:
                f.write(data_string + '\n')
            self.log(f"Data written to {data_filename}")
        except Exception as e:
            self.log(f"Error writing data to file: {str(e)}")

    def init_csv_data_cache(self):
        '''
        Returns a formatted string representation of the data cache in CSV format.
        '''
        formatted_cache = []
        header = (
            f"Tx,Time,MAC,PosX,PosY,Temp,Hum,Pres,Batt,RSSI,HopCount"
        )
        formatted_cache.append(header)
        
        for id, data in self.data_cache.items():
            pos_x, pos_y = data['pos']  # Unpack position into x and y
            formatted_data = (
                f"{self.tx_counter}," +
                f"{data['time']:.2f}," +           # Time formatted to 2 decimal places
                f"{id}," +
                f"{pos_x:.2f}," +                  # Position X
                f"{pos_y:.2f}," +                  # Position Y
                f"{data['temperature']:.2f}," +
                f"{data['humidity']:.2f}," +
                f"{data['pressure']:.2f}," +
                f"{data['battery_level']:.1f}," +  # Assuming battery level is already a percentage
                f"{data['rssi']:.1f}," +
                f"{data['hop_count']}"
            )
            formatted_cache.append(formatted_data)
        
        return "\n".join(formatted_cache)

    def format_csv_data_cache(self):
        '''
        Returns a formatted string representation of the data cache in CSV format.
        '''
        formatted_cache = []
        
        for id, data in self.data_cache.items():
            pos_x, pos_y = data['pos']  # Unpack position into x and y
            formatted_data = (
                f"{self.tx_counter}," +
                f"{data['time']:.2f}," +
                f"{id}," +
                f"{pos_x:.2f}," +
                f"{pos_y:.2f}," +
                f"{data['temperature']:.2f}," +
                f"{data['humidity']:.2f}," +
                f"{data['pressure']:.2f}," +
                f"{data['battery_level']:.1f}," +
                f"{data['rssi']:.1f}," +
                f"{data['hop_count']}"
            )
            formatted_cache.append(formatted_data)
        
        return "\n".join(formatted_cache)
    
    def init_data_cache(self):
        '''
        Returns a formatted string representation of the data cache with aligned columns.
        '''
        formatted_cache = []
        header = (
            f"Data Log:\n" +
            f"{'Tx':<4}" +
            f"{'Time':<9}" +
            f"{'MAC':<9}" +
            f"{'Position':<22}" +
            f"{'Temp':<8}" +
            f"{'Hum':<8}" +
            f"{'Pres':<8}" +
            f"{'Batt':<8}" +
            f"{'RSSI':<8}" +
            f"{'HopCount':<6}"
        )
        formatted_cache.append(header)
        formatted_cache.append('-' * 100)  # Divider line

        for id, data in self.data_cache.items():
            formatted_data = (
                f"{self.tx_counter:<4}" +
                f"{round(data['time'],3):<9.2f}" +
                f"{str(id):<9}" +
                f"{str(data['pos']):<22}" +
                f"{data['temperature']:<8.2f}" +
                f"{data['humidity']:<8.2f}" +
                f"{data['pressure']:<8}" +
                f"{data['battery_level']:<8.1f}" +  # Display battery level as percentage
                f"{data['rssi']:<8.1f}" +
                f"{data['hop_count']:<6}"
            )
            formatted_cache.append(formatted_data)

        return "\n".join(formatted_cache)

    ############################
    @property
    def now(self):
        return self.sim.env.now

###########################################################
sim = wsp.Simulator(
    until=200,
    timescale=1,
    visual=True,
    terrain_size=(350, 350),
    title="SimNet")

# Define a line style for parent links
sim.scene.linestyle("parent", color=(0, 0.8, 0), arrow="head", width=2)

# Place nodes in square grid

for x in range(int(num_nodes ** 0.5)):
    for y in range(int(num_nodes ** 0.5)):
        px = 50 + x * 60 + random.uniform(-20, 20)
        py = 50 + y * 60 + random.uniform(-20, 20)
        node = sim.add_node(MyNode, (round(px,2), round(py,2)))
        node.tx_range = 75
        node.logging = True

# Start the simulation
sim.run()
