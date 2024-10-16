import random
import math
import json
import wsnsimpy.wsnsimpy_tk as wsp

TX_RANGE = 75
GATEWAY = 0  # Gateway id
INTERVAL = 20  # Increased to allow time for replies
DELAY = 2  # Delayed execution time
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

    ###################
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
        self.battery_level = 100.0
        self.rssi = 0.0
        self.overhead = 0.0
        self.path = GATEWAY  # Path to the gateway
        self.clock_offset = 0  # Clock offset for synchronization
        self.start_flag = False
        self.data_cache = {}
        self.latency = 0

    ###################
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

                yield self.timeout(INTERVAL)
                self.log(f"COMPLETE")

                self.scene.clearlinks()
                yield self.timeout(5)
                self.tx_counter += 1

    ###################
    def send_dreq(self):
        '''
        Send a Data Request (DREQ) message to broadcast address.
        '''
        data = {
            'msg': 'dreq',
            'tx_counter': self.tx_counter,
            'battery_level': self.battery_level,
            'rssi': self.rssi,
            'overhead': self.overhead,
            'path': self.path,
            'clock': self.now
        }
        json_data = json.dumps(data).encode('utf-8')  # Encode data to JSON
        
        try:
            self.send(wsp.BROADCAST_ADDR, msg='dreq', data=json_data)
            self.log(f"SENT: DREQ from {self.id}")
        except Exception as e:
            self.log(f"ERROR: {e}")

    ###################
    def send_dreply(self, src, data_cache):
        '''
        Send a Data Reply (DREP) message to the lowest overhead node.
        '''
        json_data = json.dumps(data_cache).encode('utf-8')  # Encode data to JSON

        self.start_flag = False

        self.send(self.path, msg='dreply', src=src, data=json_data)
        self.log(f"SENT: DREP to {self.path}")

    ###################
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
                        self.send_dreq(sender, self.tx_counter, self.pos, self.rssi, self.overhead, self.path, self.now)  # Forward the DREQ message

                        self.start_flag = False
                        yield self.timeout(DELAY)
                        self.start_flag = True
                        self.start_reply() # Start the reply process again


        elif msg == 'dreply':
            self.log(f"RECIEVED: DREP from {sender}")

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
                    self.log(f"RECEIVED data from connected nodes")
                    self.log(f"\n" + self.init_data_cache())

                    self.scene.clearlinks() # Clear the links
                    #reset all the node coulors to default
                    for node in self.sim.nodes:
                        self.scene.nodecolor(node.id, 0, 0, 0)
                        self.scene.nodewidth(node.id, 1)
                    self.neighbor_table = {} # Reset the Gateway neighbor table


            else: 
                # Unrecieved branches
                pendingBranches = [key for key, neighbor in branches.items() if neighbor.get('rx', 0) == 0]
                self.log(f"WAITING FOR: {pendingBranches}")

    ###################
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

    def log_data(self):
        '''Log the collected data'''
        
        # Calcualte latency in seconds
        self.latency = self.now - self.latency
        
        # Add data to the log file
        filename = 'latency_SIM.txt'
        try:
            if self.tx_counter == 0:
                # Overwrite the file if tx_counter is 0
                mode = 'w'
                data_string = self.init_latency()

            else:
                # Append to the file if tx_counter is not 0
                mode = 'a'
                data_string = self.format_latency()
            
            with open(filename, mode) as f:
                f.write(data_string)
            self.log(f"Data written to {filename}")
        except Exception as e:
            self.log(f"Error writing data to file: {str(e)}")


        # Add data to the log file
        filename = 'data_log_SIM.txt'
        try:
            if self.tx_counter == 0:
                # Overwrite the file if tx_counter is 0
                mode = 'w'
                data_string = self.init_data_cache()

            else:
                # Append to the file if tx_counter is not 0
                mode = 'a'
                data_string = self.format_data_cache()
            
            with open(filename, mode) as f:
                f.write(data_string + '\n')
            self.log(f"Data written to {filename}")
        except Exception as e:
            self.log(f"Error writing data to file: {str(e)}")

        
        self.log(f"DATA:\n" + self.init_data_cache())

        self.log("COMPLETE")

        self.scene.clearlinks() # Clear the links
        for node in self.sim.nodes: # Reset all the node coulors to default
            self.scene.nodecolor(node.id, 0, 0, 0)
            self.scene.nodewidth(node.id, 1)

        self.start_dreq = True
        self.tx_counter += 1
        self.neighbor_table = {}  # Reset the gateway neighbor table
        self.data_cache = {}  # Reset data cache

        yield self.timeout(INTERVAL)  # Wait for INTERVAL seconds before sending the next DREQ message

    def lowest_overhead_neighbor(self):
        '''
        Returns the neighbor with the lowest overhead.
        '''
        return min(self.neighbor_table, key=lambda n: self.neighbor_table[n]['overhead'])

    def calculate_overhead(self, sender, data):
        '''
        Calculate the overhead based on battery level and RSSI.
        '''
        #mac_bytes = bytes(int(b, 16) for b in sender_mac.split(':'))

        # Parse the battery and RSSI values as floats
        received_battery = float(data['battery_level'])
        received_rssi = float(data['rssi'])

        # Apparent normalized battery level and RSSI
        self.battery_level = self.normalize_battery(self.read_battery_level()) + received_battery
        self.rssi = self.normalize_rssi(self.read_rssi(sender)) + received_rssi

        # Calculate and return the overhead
        overhead = WEIGHT * self.battery_level + (1 - WEIGHT) * self.rssi
        return overhead

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

    def is_new_transaction(self, data):
        '''If new transaction, reset the node.'''
        if data['tx_counter'] != self.tx_counter:
            self.tx_counter = data['tx_counter']
            self.neighbor_table = {}
            self.battery_level = 0.0
            self.rssi = 0.0
            self.overhead = 0.0
            self.path = GATEWAY
            self.start_flag = False
            self.reply_flag = False  # Reset reply flag
            self.reply_deadline = None  # Reset the reply deadline
            self.data_cache = {}

    def update_neighbor_table(self, sender_mac, data):
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

        self.neighbor_table[sender_mac] = {
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
        rssi = self.rssi

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

    def read_rssi(self, sender_mac):
        """
        Calculate the RSSI value based on distance using a path loss model.
        
        Parameters:
        distance (float): The distance from the transmitter in meters.
        tx_power (int): Transmit power in dBm at 1 meter. Default is -40 dBm.
        
        Returns:
        float: The RSSI value in dBm.
        """
        for dist, node in self.neighbor_distance_list:
            if node.id == sender_mac:
                distance = dist
                break  # Exit the loop once the node is found

        tx_power = -40  # Transmit power in dBm at 1 meter

        # Path loss exponent (environmental factor), typically ranges from 2 (free space) to 4 (indoor)
        path_loss_exponent = 2.5
        
        if distance <= 0:
            return tx_power
        
        # Friis transmission equation simplified for RSSI
        self.rssi = tx_power - (10 * path_loss_exponent * math.log10(distance))
        return self.rssi

    def normalize_battery(self, battery_level):
        '''
        Normalize the battery level between 0 and 1.
        '''
        normalized = (battery_level - (100)) / (0 - (100))  # Assuming battery range 100 to 0 
        normalized = min(max(normalized, 0.0), 1.0)  # Clamp between 0 and 1
        return 1.0 - battery_level  # Lower battery level means higher overhead

    def normalize_rssi(self, rssi):
        '''
        Normalize RSSI value between 0 and 1.
        '''
        normalized = (rssi - (-124)) / (-0 - (-124))  # Assuming RSSI range -124 dBm to 0 dBm
        normalized = min(max(normalized, 0.0), 1.0)  # Clamp between 0 and 1
        return 1.0 - normalized  # Lower RSSI (farther away) means higher overhead

    def log(self, msg):
        print(f"Node {'#'+str(self.id):4}[{self.now:10.5f}] {msg}")

    def init_latency(self):
        '''
        Returns a formatted string representation 
        '''
        formatted_cache = []
        header = (
            f"Latency Log:\n" +
            f"{'Tx':<4}" +
            f"{'Time':<9}"
        )
        formatted_cache.append(header)
        formatted_cache.append('-' * 100)  # Divider line

        formatted_data = (
            f"{self.tx_counter:<4}" +
            f"{self.latency:<9.2}" 
        )
        formatted_cache.append(formatted_data)

        return "\n".join(formatted_cache)

    def format_latency(self):
        '''
        Returns a formatted string representation of the data cache with aligned columns.
        '''
        formatted_cache = []

        formatted_data = (f"\n" +  
            f"{self.tx_counter:<4}" +
            f"{self.latency:<9.2}" 
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
            f"{'Pressure':<12}" +
            f"{'Batt':<6}" +
            f"{'RSSI':<6}" +
            f"{'HopCount':<6}"
        )
        formatted_cache.append(header)
        formatted_cache.append('-' * 100)  # Divider line

        for id, data in self.data_cache.items():
            formatted_data = (
                f"{self.tx_counter:<4}" +
                f"{data['time']:<9.2}" +
                f"{str(id):<9}" +
                f"{str(data['pos']):<22}" +
                f"{data['temperature']:<8.2f}" +
                f"{data['humidity']:<8.2f}" +
                f"{data['pressure']:<12.2f}" +
                f"{data['battery_level'] * 100:<6.1f}" +  # Display battery level as percentage
                f"{data['rssi']:<6.1}" +
                f"{data['hop_count']:<6}"
            )
            formatted_cache.append(formatted_data)

        return "\n".join(formatted_cache)

    def format_data_cache(self):
        '''
        Returns a formatted string representation of the data cache with aligned columns.
        '''
        formatted_cache = []

        for id, data in self.data_cache.items():
            formatted_data = (
                f"{self.tx_counter:<4}" +
                f"{data['time']:<9}" +
                f"{str(id):<9}" +
                f"{str(data['pos']):<22}" +
                f"{data['temperature']:<8.2f}" +
                f"{data['humidity']:<8.2f}" +
                f"{data['pressure']:<12.2f}" +
                f"{data['battery_level'] * 100:<6.1f}" +  # Display battery level as percentage
                f"{data['rssi']:<6.1}" +
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
