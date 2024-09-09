import simpy
import random
import matplotlib.pyplot as plt
import math

class Node:
    def __init__(self, env, node_id, position, initial_battery, transmission_range, t_mac_interval):
        self.env = env  # Simulation environment
        self.node_id = node_id  # Unique identifier for the node
        self.position = position  # Position of the node in the network
        self.battery = initial_battery  # Initial battery level
        self.transmission_range = transmission_range  # Maximum transmission range
        self.data_queue = []  # Queue to store generated data
        self.neighbors = []  # List of neighboring nodes
        self.process = env.process(self.run())  # Start the node process
        self.t_mac_interval = t_mac_interval  # T-MAC interval for sleep-wake cycles
        self.active = True  # Indicates if the node is active or in sleep mode

    def run(self):
        while True:
            if self.battery > 0:
                self.get_clock_info()
                self.generate_data()
                yield self.env.timeout(10)  # Generate data every 10 time units
                self.transmit_data()
                yield self.env.timeout(self.t_mac_interval)  # T-MAC interval
                self.check_activity()
            else:
                print(f'Node {self.node_id} is out of battery.')
                break

    def get_clock_info(self):
        # Simulate obtaining clock information from the DS3231 Real Time Clock Module
        current_time = self.env.now
        print(f'Node {self.node_id} obtained clock info: current time is {current_time}')
        return current_time

    def generate_data(self):
        data = f"Data from node {self.node_id} at time {self.env.now}"
        self.data_queue.append(data)  # Add generated data to the queue
        self.battery -= 0.1  # Power consumption to generate data
        print(f'Node {self.node_id} generated data: {data}')

    def transmit_data(self):
        if self.data_queue and self.neighbors:
            data = self.data_queue.pop(0)  # Get data from the queue
            print(f'Node {self.node_id} transmitting data: {data}')
            self.battery -= 0.5  # Power consumption to transmit data
            for neighbor in sorted(self.neighbors, key=lambda n: self.routing_metric(n)):
                if self.in_range(neighbor):
                    neighbor.receive_data(data)  # Transmit data to the best neighbor
                    break

    def receive_data(self, data):
        print(f'Node {self.node_id} received data: {data}')
        self.data_queue.append(data)  # Add received data to the queue
        self.battery -= 0.2  # Power consumption to receive data

    def in_range(self, other_node):
        return self.distance_to(other_node) <= self.transmission_range  # Check if the node is within range

    def distance_to(self, other_node):
        return math.sqrt((self.position[0] - other_node.position[0])**2 + 
                         (self.position[1] - other_node.position[1])**2)  # Calculate the distance to another node

    def routing_metric(self, neighbor):
        distance_weight = 0.5
        energy_weight = 0.5
        return distance_weight * self.distance_to(neighbor) - energy_weight * neighbor.battery  # Combine distance and battery level in routing decisions

    def check_activity(self):
        if not self.data_queue:
            self.go_to_sleep()  # Enter sleep mode if no data to process

    def go_to_sleep(self):
        self.active = False
        print(f'Node {self.node_id} going to sleep to save energy.')
        self.env.timeout(self.t_mac_interval)  # Sleep for the T-MAC interval

    def wake_up(self):
        self.active = True
        print(f'Node {self.node_id} waking up.')

class Network:
    def __init__(self, env, num_nodes, area_size, t_mac_interval):
        self.env = env  # Simulation environment
        self.nodes = []  # List of nodes in the network
        self.num_nodes = num_nodes  # Number of nodes in the network
        self.area_size = area_size  # Size of the area for node deployment
        self.t_mac_interval = t_mac_interval  # T-MAC interval for all nodes
        self.deploy_nodes()
        self.connect_nodes()

    def deploy_nodes(self, use_fixed_positions=True):
        fixed_positions = [(800, 500), (600, 700), (600, 500), (600, 300),
                           (400, 800), (400, 600), (400, 400), (400, 200), 
                           (200, 600), (200, 400)]  # Fixed positions for 10 nodes
        for i in range(self.num_nodes):
            if use_fixed_positions:
                position = fixed_positions[i % len(fixed_positions)]
            else:
                position = (random.uniform(0, self.area_size), random.uniform(0, self.area_size))
            node = Node(self.env, i, position, 100, 300, self.t_mac_interval)  # Create and add nodes to the network
            self.nodes.append(node)

    def connect_nodes(self):
        for node in self.nodes:
            for potential_neighbor in self.nodes:
                if node != potential_neighbor and node.in_range(potential_neighbor):
                    node.neighbors.append(potential_neighbor)  # Connect nodes within range

    def plot_network(self):
        plt.figure(figsize=(8, 8))
        for node in self.nodes:
            # Color-code nodes based on battery levels and status
            color = 'green' if node.active else 'red'
            plt.scatter(*node.position, c=color, s=100)
            plt.text(node.position[0], node.position[1], f'{node.node_id}', fontsize=12, ha='right')
        for node in self.nodes:
            for neighbor in node.neighbors:
                plt.plot([node.position[0], neighbor.position[0]], [node.position[1], neighbor.position[1]], 'gray')
        plt.title("Network Topology")
        plt.xlim(0, self.area_size)
        plt.ylim(0, self.area_size)
        plt.show()

    def print_battery_levels(self):
        sorted_nodes = sorted(self.nodes, key=lambda node: node.battery, reverse=True)
        print("Battery levels of nodes (sorted):")
        for node in sorted_nodes:
            print(f"Node {node.node_id}: {node.battery} mAh")

def run_simulation(num_nodes, area_size, simulation_time, t_mac_interval):
    env = simpy.Environment()  # Create a simulation environment
    network = Network(env, num_nodes, area_size, t_mac_interval)  # Create a network
    env.run(until=simulation_time)  # Run the simulation
    network.plot_network()  # Plot the network topology
    network.print_battery_levels()  # Print battery levels of nodes

if __name__ == "__main__":
    num_nodes = 10  # Number of nodes in the network
    area_size = 1000  # Size of the area for node deployment``
    simulation_time = 50  # Duration of the simulation
    t_mac_interval = 5  # T-MAC interval for sleep-wake cycles

    run_simulation(num_nodes, area_size, simulation_time, t_mac_interval)
