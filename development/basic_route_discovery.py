import random
import wsnsimpy.wsnsimpy_tk as wsp

SOURCE = 0
DEST = 15

###########################################################
def delay():
    '''
    Returns a random delay between 0.2 and 0.8 seconds.
    '''
    return random.uniform(0.2, 0.8)

###########################################################
class MyNode(wsp.LayeredNode):
    tx_range = 100  # Transmission range of the node

    ###################
    def init(self):
        '''
        Initialize the node, setting previous node to None.
        '''
        super().init()
        self.prev = None

    ###################
    def run(self):
        '''
        Main loop for the node. Sets the color and width of the node based on its role (SOURCE, DEST, or other).
        '''
        if self.id == SOURCE:
            self.scene.nodecolor(self.id, 0, 0, 1)  # Set the color of the source node to blue
            self.scene.nodewidth(self.id, 2)
            yield self.timeout(1)
            self.send_rreq(self.id)
        elif self.id == DEST:
            self.scene.nodecolor(self.id, 1, 0, 0)  # Set the color of the destination node to red
            self.scene.nodewidth(self.id, 2)
        else:
            self.scene.nodecolor(self.id, 0.7, 0.7, 0.7)  # Set the color of other nodes to gray

    ###################
    def send_rreq(self, src):
        '''
        Send a Route Request (RREQ) message to broadcast address.
        '''
        self.send(wsp.BROADCAST_ADDR, msg='rreq', src=src)

    ###################
    def send_rreply(self, src):
        '''
        Send a Route Reply (RREP) message to the previous node.
        '''
        if self.id != DEST:
            self.scene.nodecolor(self.id, 0, 0.7, 0)  # Set the color of the node to green
            self.scene.nodewidth(self.id, 2)
        self.send(self.prev, msg='rreply', src=src)

    ###################
    def start_send_data(self):
        '''
        Start sending data packets periodically.
        '''
        self.scene.clearlinks()
        seq = 0
        while True:
            yield self.timeout(1)
            self.log(f"Send data to {DEST} with seq {seq}")
            self.send_data(self.id, seq)
            seq += 1

    ###################
    def send_data(self, src, seq):
        '''
        Forward data packets to the next node in the route.
        '''
        self.log(f"Forward data with seq {seq} via {self.next}")
        self.send(self.next, msg='data', src=src, seq=seq)

    ###################
    def on_receive(self, sender, msg, src, **kwargs):
        '''
        Handle received messages and act based on the message type.
        '''
        if msg == 'rreq':
            if self.prev is not None: return
            self.prev = sender
            self.scene.addlink(sender, self.id, "parent")
            if self.id == DEST:
                self.log(f"Receive RREQ from {src}")
                yield self.timeout(5)
                self.log(f"Send RREP to {src}")
                self.send_rreply(self.id)
            else:
                yield self.timeout(delay())
                self.send_rreq(src)

        elif msg == 'rreply':
            self.next = sender
            if self.id == SOURCE:
                self.log(f"Receive RREP from {src}")
                yield self.timeout(5)
                self.log("Start sending data")
                self.start_process(self.start_send_data())
            else:
                yield self.timeout(0.2)
                self.send_rreply(src)

        elif msg == 'data':
            if self.id != DEST:
                yield self.timeout(0.2)
                self.send_data(src, **kwargs)
            else:
                seq = kwargs['seq']
                self.log(f"Got data from {src} with seq {seq}")

###########################################################
sim = wsp.Simulator(
    until=100,
    timescale=1,
    visual=True,
    terrain_size=(540, 540),
    title="VineNet Sim")

# Define a line style for parent links
sim.scene.linestyle("parent", color=(0, 0.8, 0), arrow="tail", width=2)

# Place nodes over 100x100 grids
for x in range(4):
    for y in range(4):
        px = 50 + x * 60 + random.uniform(-20, 20)
        py = 50 + y * 60 + random.uniform(-20, 20)
        node = sim.add_node(MyNode, (px, py))
        node.tx_range = 75
        node.logging = True

# Start the simulation
sim.run()
