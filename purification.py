import netsquid as ns

from ms_protocol import MSProtocol

class PurificationProtocol(ns.protocols.NodeProtocol):
    PURIFICATION_SIGNAL = "purification_signal"
    PURIFICATION_SIGNAL_EVT_TYPE = ns.pydynaa.EventType("purification signal", "The purification is terminated")

    @staticmethod
    def _get_purification_program():
        # create a program that will be used to purify the qubits
        program = ns.components.QuantumProgram(num_qubits=2)                # the quantum program acts on 2 qubits
        q1, q2 = program.get_qubit_indices(2)                               # retrieve the qubits indices
        program.apply(ns.components.INSTR_CX, [q1, q2])                     # apply a cnot gate to both qubits
        program.apply(ns.components.INSTR_MEASURE, q2, output_key="M0")     # apply a mesaurement to the second qubit
        return program
    
    def __init__(self, node, name=None, K_attempts=200, t_clock=10, link_length=25, connection=None, nic_index = 0):
        super().__init__(node=node, name=name)

        self.add_signal(self.PURIFICATION_SIGNAL, self.PURIFICATION_SIGNAL_EVT_TYPE)
        
        if (nic_index == 0):        # execution on left side of repeater or end node 
            # we must perform the MS protocol for each quantum memory slot
            self.add_subprotocol(MSProtocol(self.node, name="MS0", K_attempts=K_attempts, length=link_length, t_clock=t_clock,
                                            connection=connection, mem_position=0, nic_index=nic_index), name="MSProtocol_0")
            self.add_subprotocol(MSProtocol(self.node, name="MS1", K_attempts=K_attempts, length=link_length, t_clock=t_clock,
                                            connection=connection, mem_position=1, nic_index=nic_index), name="MSProtocol_1")
            self.qmemory_pos0 = 0
            self.qmemory_pos1 = 1
            self.node_cport = self.node.ports['c0']
            
        else:                       # execution on right side of repeater
            # we must perform the MS protocol for each quantum memory slot
            self.add_subprotocol(MSProtocol(self.node, name="MS0", K_attempts=K_attempts, length=link_length, t_clock=t_clock,
                                            connection=connection, mem_position=2, nic_index=nic_index), name="MSProtocol_0")
            self.add_subprotocol(MSProtocol(self.node, name="MS1", K_attempts=K_attempts, length=link_length, t_clock=t_clock,
                                            connection=connection, mem_position=3, nic_index=nic_index), name="MSProtocol_1")
            self.qmemory_pos0 = 2
            self.qmemory_pos1 = 3
            self.node_cport = self.node.ports['c1']
        
    def _get_fidelity(self, position):
        # we read without popping the qubit, cheating because we cannot access the state of a qubit without measure
        qubits = self.node.qmemory.peek(positions=[position])[0].qstate.qubits
        fidelity = ns.qubits.qubitapi.fidelity(qubits, ns.qubits.ketstates.b00, squared=True)
        return fidelity
    
    def run(self):
        # create the entangled pair on the first memory slot
        self.subprotocols["MSProtocol_0"].start()

        # wait for the first MSProtocol to finish
        yield self.await_signal(sender=self.subprotocols["MSProtocol_0"], signal_label = MSProtocol.ENTANGLED_SIGNAL)

        # start the second MSProtocol to entangle the second qubit
        self.subprotocols["MSProtocol_1"].start()
        yield self.await_signal(sender=self.subprotocols["MSProtocol_1"], signal_label = MSProtocol.ENTANGLED_SIGNAL)

        # get the fidelity of the qubits
        fidelity_0 = self._get_fidelity(self.qmemory_pos0)
        fidelity_1 = self._get_fidelity(self.qmemory_pos1)

        # print the fidelities
        print(f"[{ns.sim_time()}] Repeater {self.node.ID}: Both qubits are entangled with fidelity {fidelity_0} and {fidelity_1}")

        # at this point we have two entangled qubits in the memory
        prog = self._get_purification_program()
        self.node.qmemory.execute_program(prog, qubit_mapping=[self.qmemory_pos0, self.qmemory_pos1], error_on_fail=True)
        yield self.await_program(self.node.qmemory)

        # we collect the measurement result
        outcome = prog.output["M0"][0]

        # we send the measurement to the other node
        self.node_cport.tx_output(ns.components.Message(items=outcome))

        # we wait from the measurement result from the other node
        yield self.await_port_input(self.node_cport)
        msg = self.node_cport.rx_input()
        outcome_other = msg.items[0]

        # we check if the measurement are the same
        if outcome == outcome_other:
            print(f"[{ns.sim_time()}] Purification successful")
            # print the new qubit fidelity with respect to the bell state
            print(f"[{ns.sim_time()}] Fidelity of the new qubit pair with respect to the Bell state: {self._get_fidelity(position=self.qmemory_pos0)}")
            self.send_signal(self.PURIFICATION_SIGNAL, result = True)
        else:
            print(f"[{ns.sim_time}] Purification failed")
            # discard the qubit from memory
            # self.node.qmemory.pop(positions=self.qmemory_pos0)
            self.send_signal(self.PURIFICATION_SIGNAL, result = False)


        