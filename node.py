import netsquid as ns 

class NetNode(ns.nodes.Node):
    """
    This class implements a quantum network node
    """

    def __init__(self, ID, name, is_repeater = True):
        if is_repeater:
            port_names = ["q0", "c0", "q1", "c1"]
        else:
            port_names = ["q0", "c0"]
        
        super().__init__(name = name, ID = ID, port_names = port_names)

        if is_repeater: 
            physical_instructions = [
                ns.components.PhysicalInstruction(ns.components.INSTR_CX, duration=1., parallel=True),
                ns.components.PhysicalInstruction(ns.components.INSTR_MEASURE, duration=1., parallel=True),
                ns.components.PhysicalInstruction(ns.components.INSTR_MEASURE_BELL, duration=1.)
            ]
            self.qmemory = ns.components.QuantumProcessor("qproc", num_positions=4, phys_instructions=physical_instructions)
        else:
            physical_instructions = [
                ns.components.PhysicalInstruction(ns.components.INSTR_CX, duration=1., parallel=True),
                ns.components.PhysicalInstruction(ns.components.INSTR_MEASURE, duration=1., parallel=True),
            ]
            self.qmemory = ns.components.QuantumProcessor("qproc", num_positions=2, phys_instructions=physical_instructions)