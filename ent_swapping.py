import netsquid as ns

from purification import PurificationProtocol

class EntSwapping(ns.protocols.NodeProtocol):
    @staticmethod
    def _get_bsm_program():
        program = ns.components.QuantumProgram(num_qubits=2)
        q1, q2 = program.get_qubit_indices(2)
        program.apply(ns.components.INSTR_MEASURE_BELL, [q1, q2], output_key="M")
        
        return program
    
    def __init__(self, node, to_wait, name=None, is_left=True):
        super().__init__(node=node, name=name)
        self.is_left = is_left
        self.to_wait = to_wait

    def run(self): 
        # I wait for the entanglement eventually purified
        for to_wait in self.to_wait:
                yield self.await_signal(sender=to_wait, signal_label = PurificationProtocol.PURIFICATION_SIGNAL)

        if self.is_left:
            # i'm the left node, so I execute the BSM on qubit 0 (1 is measured during purification) and 2
            prog = self._get_bsm_program()
            self.node.qmemory.execute_program(prog, qubit_mapping=[0, 2], error_on_fail=True)
            yield self.await_program(self.node.qmemory)
            
            # the ouptut of the measurement is sent to the right node
            outcome = prog.output["M"]
            self.node.ports['c1'].tx_output(ns.components.Message(items=outcome))

        else:
            # wait to receive the ouput of the bsm from the left node
            yield self.await_port_input(self.node.ports['c0'])
            msg = self.node_cport.rx_input()
            measurement = msg.items

            # infer the output bell state and print it (?)
            print(f"[{ns.sim_time()}] Right end-node {self.node.ID}: I'm entangled with the left end-node with state {self.node.qmemory.peek(positions=[0])[0].qstate.qubits}")



        


        

    