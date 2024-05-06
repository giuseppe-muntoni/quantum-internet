import netsquid as ns

from purification import PurificationProtocol

class EntSwapping(ns.protocols.NodeProtocol):
    READY_TO_SWAPPING_SIGNAL = "swapping ready to start signal"
    READY_TO_SWAPPING_SIGNAL_EVT_TYPE = ns.pydynaa.EventType("swapping ready to start signal", "I'm ready to start the entanglement swapping")

    @staticmethod
    def _get_bsm_program():
        program = ns.components.QuantumProgram(num_qubits=2)
        q1, q2 = program.get_qubit_indices(2)
        program.apply(ns.components.INSTR_MEASURE_BELL, [q1, q2], output_key="M")
        
        return program
    
    def __init__(self, node, purif_to_wait, name=None, is_left=True):
        super().__init__(node=node, name=name)
        self.is_left = is_left
        self.purif_to_wait = purif_to_wait

        self.add_signal(self.READY_TO_SWAPPING_SIGNAL, self.READY_TO_SWAPPING_SIGNAL_EVT_TYPE)
        
        for to_wait in self.purif_to_wait: 
            self.add_subprotocol(to_wait)

    def set_swap_to_wait(self, swap_to_wait):
        self.swap_to_wait = swap_to_wait

    def run(self): 
        # I wait for the entanglement eventually purified
        for to_wait in self.purif_to_wait:
            print(f"[{ns.sim_time()}] Node {self.node.name}: waiting for purification protocol {to_wait.name} to terminate")
            yield self.await_signal(sender=to_wait, signal_label = PurificationProtocol.PURIFICATION_SIGNAL)
        
        self.send_signal(self.READY_TO_SWAPPING_SIGNAL)
        yield self.await_signal(sender=self.swap_to_wait, signal_label = self.READY_TO_SWAPPING_SIGNAL)

        print(f"[{ns.sim_time()}] Node {self.node.name}: starting the swapping")

        if self.is_left:
            # i'm the left node, so I execute the BSM on qubit 0 (1 is measured during purification) and 2
            prog = self._get_bsm_program()
            self.node.qmemory.execute_program(prog, qubit_mapping=[0, 2], error_on_fail=True)
            yield self.await_program(self.node.qmemory)
            
            # the ouptut of the measurement is sent to the right node
            outcome = prog.output["M"]
            print(f"[{ns.sim_time()}] Node {self.node.name}: sending in output the BSM {outcome[0]}")
            self.node.ports['c1'].tx_output(ns.components.Message(items=outcome))

        else:
            # wait to receive the ouput of the bsm from the left node
            yield self.await_port_input(self.node.ports['c0'])
            msg = self.node.ports['c0'].rx_input()
            measurement = msg.items[0]

            if (measurement == 0):
                final_state = ns.qubits.ketstates.b00
            elif (measurement == 1):
                final_state = ns.qubits.ketstates.b01
            elif (measurement == 2):
                final_state = ns.qubits.ketstates.b10
            else:
                final_state = ns.qubits.ketstates.b11

            print(f"[{ns.sim_time()}] Node {self.node.name}: I'm entangled with the left end-node with state {final_state}")




        


        

    