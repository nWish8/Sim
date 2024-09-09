import random
import wsnsimpy.wsnsimpy_tk as wsp

GATEWAY = 0
num_nodes = 25

###########################################################
def randdelay():
    '''
    Returns a random delay between 0.2 and 0.6 seconds.
    '''
    return random.uniform(0.2, 0.6)

###########################################################
class MyNode(wsp.LayeredNode):
    tx_range = 75  # Transmission range of the node

    ###################
    def init(self):
        '''
        Initialize the node, setting previous node to None.
        '''
        super().init()
        self.cntr = 0
        self.neighbor_table = {}  # Dictionary to store neighbors and their costs
        self.cost = 1
        self.clk_offset = 0  # Clock offset for synchronization
        self.strt_flag = False
        self.branch_flag = False
        self.delayCache = {}
        self.dataCache = ""

    ###################
    def run(self):
        '''
        Main loop for the node. Sets the color and width of the node based on its role (SOURCE, DEST, or other).
        '''
        if self.id == GATEWAY:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the source node to blue
            self.scene.nodewidth(self.id, 2)
            self.cntr = 0
            yield self.timeout(1)
            while True:
                self.send_rreq(self.id, self.cntr, self.cost, sim.env.now)
                self.log(f"RREQ sent from {self.id}")
                yield self.timeout(180)
                self.scene.clearlinks()
                self.log(f"COMPLETE")
                yield self.timeout(5)
                self.cntr += 1

    ###########################################################
    def delay(self):
        '''
        Returns a delay based on the cost function.
        '''
        return 0.2 + (2*num_nodes) / (self.cost+3)
    
    ###########################################################
    def branchdelay(self):
        '''
        Returns a delay based on the cost function.
        '''
        return (self.delayCache[1]/(num_nodes-2))/self.delayCache[2]

    ###################
    def send_rreq(self, src, cntr, cost, clk):
        '''
        Send a Route Request (RREQ) message to broadcast address.
        '''
        self.send(wsp.BROADCAST_ADDR, msg='rreq', src=src, cntr=cntr, cost=cost, clk=clk)

    ###################
    def send_rreply(self, src):
        '''
        Send a Route Reply (RREP) message to the previous node.
        '''
        if self.id != GATEWAY:
            self.scene.nodecolor(self.id, 0, 0.7, 0)  # Set the color of the node to green
            self.scene.nodewidth(self.id, 2)
        next = min(self.neighbor_table, key=self.neighbor_table.get)
        self.send(next, msg='rreply', src=src)

    ###################
    def send_data(self, src, seq):
        '''
        Forward data packets to the next node in the lowest cost route.
        '''
        
        # Get the index of the lowest cost neighbor
        next = self.lowestCostNeighbor()
        
        # Forward the data packet to the next node
        self.send(next, msg='data', src=src, seq=seq)

        self.strt_flag = False
        self.branch_flag = False
        self.log(f"Data Reply: flags False")

    ###################
    def on_receive(self, sender, msg, src, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''

        if msg == 'rreq':
            if kwargs['cntr'] != self.cntr:
                self.cntr = kwargs['cntr']
                self.neighbor_table = {}
                self.cost = 1
                self.delayCache = {}
                self.branch_flag = False
                self.strt_flag = False
                self.dataCache = ""

            if self.id == GATEWAY: return # If this node is the gateway, return
            new_cost = self.calculate_cost() + kwargs['cost']  # Calculate node cost
            
            if not self.neighbor_table : # First RREQ message received
                self.neighbor_table[sender] = kwargs['cost'] # Add the sender to the neighbor table
                self.scene.addlink(sender, self.id, "parent") # Add a link between the sender and this node
                self.cost = new_cost  # Update the node's cost to the gateway
                yield self.timeout(randdelay())
                self.send_rreq(src, self.cntr, self.cost, sim.env.now) # Forward the RREQ message
                self.strt_flag = True
                self.dataCache = f"Path : {self.id}"
                #self.timeout(num_nodes*0.3)
                self.data_reply()  # Start the reply process

            if self.neighbor_table:  # Node has received a RREQ message before
                if sender not in self.neighbor_table or kwargs['cost'] < self.neighbor_table[sender]:
                    self.neighbor_table[sender] = kwargs['cost']  # Update the neighbor table
                    self.scene.addlink(sender, self.id, "parent")

                    if kwargs['cost'] < self.neighbor_table[self.lowestCostNeighbor()]:
                        self.cost = new_cost  # Update Node cost
                        yield self.timeout(randdelay())
                        self.send_rreq(src, self.cntr, self.cost, sim.env.now)  # Forward the RREQ message
                        self.strt_flag = False
                        yield self.timeout(self.delayCache[1])
                        self.strt_flag = True
                        init = f"Path : {self.id}"
                        self.data_reply() # Start the reply process again


        elif msg == 'rreply':
            self.next = sender
            if self.id == GATEWAY:
                self.log(f"Receive RREP from {src}")
                yield self.timeout(5)
                self.log("Start sending data")
                #self.start_process(self.start_send_data())
            else:
                yield self.timeout(0.2)
                self.send_rreply(src)

        elif msg == 'data':
            if self.id != GATEWAY:                
                self.log(f"RECIEVED:\nNode {'#'+str(self.id):4}[----.-----] {kwargs['seq']}")

                if self.branch_flag: # If another data packet is recieved before send add to the sequence
                    self.log(f"RECIEVED: branch_flag = True")

                    self.dataCache = kwargs['seq'] + f">>{self.id}\n" + f"Node {'#'+str(self.id):4}[----.-----] " + self.dataCache # Add the node id to the sequence                  
                    self.log(f"RECIEVED: dataCache Updated")
                    
                    self.log(f"RECIEVED: Branch.. current delay at {self.delayCache[0] + self.delayCache[1]}")
                    new_delay = self.branchdelay()
                    self.log(f"RECIEVED: Branch.. new delay at {self.now + new_delay}")
                    self.delayCache[2] =+ 1
                    self.log(f"RECIEVED: Branch.. num_branch {self.delayCache[2]}")
                    self.data_reply()
                    #self.log(f"RECIEVED: Branch.. delay set")
                    return

                # Add data to seq
                self.dataCache = kwargs['seq'] + f">{self.id}"
                self.log(f"RECIEVED: dataCache Updated:")
                self.log(f"{self.dataCache}")
                new_delay = self.branchdelay()
                self.log(f"RECIEVED: new delay at {self.now + new_delay}")
                self.branch_flag = True
                self.log(f"Set branch flag true")
                self.data_reply()

            else:
                self.log(kwargs['seq'] + f">{self.id}")
                self.log(f"#{self.cntr} : Collection Success")

    ###################
    def delayed_exec(self, delay, func, *args, **kwargs):
        '''Execute a function after a delay.'''
        return self.sim.delayed_exec(delay, func, *args, **kwargs)

    ###################
    def data_reply(self):
        '''The reply process'''
        def start():
            if self.strt_flag:
                # Send the DREP message
                self.log(f"Data Reply: strt_flag True")
                self.send_data(self.id, self.dataCache)
                self.log(f"SENT: data with seq:")
                self.log(f"{self.dataCache}")

        if self.branch_flag == False:
            self.log(f"Data Reply: branch_flag False")
            self.delayCache[0] = self.now
            self.delayCache[1] = self.delay()
            self.delayCache[2] = 1
        self.log(f"Data Reply: Reply cache {self.delayCache} $ {self.cost}")
        self.delayed_exec(self.delayCache[1], start)

    ###################
    def lowestCostNeighbor(self):
        '''
        Returns the neighbor with the lowest cost
        '''
        # self.log(f"Neighbor table: {self.neighbor_table}")
        return min(self.neighbor_table, key=self.neighbor_table.get)
    
    ###################
    def highestCostNeighbor(self):
        '''
        Returns the neighbor with the highest cost
        '''
        return max(self.neighbor_table, key=self.neighbor_table.get)

    ###################
    def calculate_cost(self):
        '''
        Dummy cost calculation.
        '''
        battery_level = 0.85  # Simulate battery level
        rssi = 0.7  # Simulate RSSI in -dBm
        distance = 40/50  # Simulate distance
        return (battery_level + rssi + distance)/3  # Calculate and return the cost

###########################################################
sim = wsp.Simulator(
    until=200,
    timescale=1,
    visual=True,
    terrain_size=(700, 700),
    title="VineNet Sim")

# Define a line style for parent links
sim.scene.linestyle("parent", color=(0, 0.8, 0), arrow="head", width=2)

# Place nodes in square grid

for x in range(int(num_nodes ** 0.5)):
    for y in range(int(num_nodes ** 0.5)):
        px = 50 + x * 60 + random.uniform(-20, 20)
        py = 50 + y * 60 + random.uniform(-20, 20)
        node = sim.add_node(MyNode, (px, py))
        node.tx_range = 75
        node.logging = True

# Start the simulation
sim.run()
