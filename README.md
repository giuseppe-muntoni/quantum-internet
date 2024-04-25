# Quantum internet simulation
This projects aims to simulate the establishement of an e2e connection between two nodes, arbitrary distant, that wants to perform quantum communication.
The simple network simulated has two end nodes and one repeater in the middle.
The following steps are performed:
- In each node is performed the Midpoint-source protocol to generate entanglement with the subsequent node.
- Purification is performed to improve the fidelity.
- Finally, entanglement swapping is performed, so that both end node have qubits entangled to be used in quantum teleportation to communicate.