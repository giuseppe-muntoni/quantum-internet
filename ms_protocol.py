import netsquid as ns
import math

def get_EPS_connection(t_clock, p_m, length, p_lr) :

    # create the EPS connection
    eps_conn = ns.nodes.Connection(name = "eps_conn")

    # define the EPS
    # with probability p_m a bell state is generated
    state_sampler = ns.qubits.StateSampler([ns.qubits.ketstates.b00, None], [p_m, 1 - p_m])
    
    # t_clock is in nsecs so is equal to 10e9 * x but the frequency is in the inverse of seconds so I put 10e9 on the numerator to obtain 1 / x 
    eps = ns.components.QSource(name = "EPS", 
                                state_sampler = state_sampler,
                                frequency = 10e9 / t_clock,
                                num_ports=2,
                                status = ns.components.SourceStatus.OFF)
    
    # define the left and right channel
    loss_model = ns.components.models.FibreLossModel(p_loss_init = 1 - p_lr, p_loss_length = 0.)
    delay_model = ns.components.models.FibreDelayModel()
    noise_model = ns.components.models.DepolarNoiseModel(depolar_rate = 0.1, time_independent = True)

    models = {"delay_model": delay_model, "quantum_loss_model": loss_model, "quantum_noise_model": noise_model}

    left_channel = ns.components.QuantumChannel(name = "left_channel", length = length/2, models = models)
    right_channel = ns.components.QuantumChannel(name = "right_channel", length = length/2, models = models)

    # add components to the connection
    eps_conn.add_subcomponent(component = eps, name = "EPS")

    eps_conn.add_subcomponent(component = left_channel, name = "left_channel")
    left_channel.ports["recv"].forward_output(eps_conn.ports["A"])

    eps_conn.add_subcomponent(component = right_channel, name = "right_channel")
    right_channel.ports["recv"].forward_output(eps_conn.ports["B"])

    # connect the EPS to the channel
    eps.ports["qout0"].connect(left_channel.ports["send"])
    eps.ports["qout1"].connect(right_channel.ports["send"])

    return eps_conn

class MSProtocol(ns.protocols.NodeProtocol):

    ENTANGLED_SIGNAL = "new _entanglement"
    ENTANGLED_SIGNAL_EVT_TYPE = ns.pydynaa.EventType("new_entangled_pair", "A new entangled pair has been delivered")

    def __init__(self, node, name, K_attempts, length, t_clock, connection = None, mem_position = 0, nic_index = 0):
        super().__init__(node = node, name = name)

        self.K_attempts = K_attempts
        self.length = length
        self.t_clock = t_clock
        self.connection = connection
        self.add_signal(self.ENTANGLED_SIGNAL, self.ENTANGLED_SIGNAL_EVT_TYPE)
        self.mem_position = mem_position

        if (nic_index == 0):        # execution on left side of repeater or end node
            self.node_qport = self.node.ports['q0']
            self.node_cport = self.node.ports['c0']
        else:                       # execution on right side of repeater
            self.node_qport = self.node.ports['q1']
            self.node_cport = self.node.ports['c1']

    def run(self):
        t_link = self.length/200000 #seconds

        # set the status of the quantum source to INTERNAL:
        # it means that the quantum source starts to emits photons at the frequency specified as param.
        # EXTERNAL means that the frequency and so the clock cycle is not considered, 
        # but the photons are generated when some external thing triggers the generation
        # Here I'm cheating because I'm accessing from the repeater (where the protocol is actually executed), the EPS status, that is outside,
        # maybe kilometers far away. It's ok for simulation purposes.
        if self.connection is not None:
            self.connection.subcomponents["EPS"].status = ns.components.SourceStatus.INTERNAL
            yield self.await_port_input(self.node_qport)
            
            # tell the other node the starting time
            start_time = math.ceil(ns.sim_time() + t_link * (10 ** 9))
            # round up to a few nanoseconds before the next clock cycle
            start_time = start_time + (self.t_clock - start_time % self.t_clock) + self.t_clock - 1
            print(f"[{ns.sim_time()}] Repeater {self.node.ID}: Sending START message with value {start_time}")
            self.node_cport.tx_output(ns.components.Message(items=["START", start_time]))
        else:
            yield self.await_port_input(self.node_cport)
            msg = self.node_cport.rx_input()

            assert msg.items[0] == "START"

            start_time = msg.items[1]

        yield self.await_timer(end_time = start_time)

        t_total_attempts = self.K_attempts * self.t_clock + ns.sim_time() + 5

        success_index = None

        while True:
            ev_expr = yield self.await_port_input(self.node_qport) | self.await_timer(end_time = t_total_attempts)

            if ev_expr.first_term.value and success_index is None:
                # compute the current attempt index
                current_attempt = math.floor((ns.sim_time() - start_time) / self.t_clock)
                # retrieve the qubit
                qubit = self.node_qport.rx_input().items[0]
                # store in qmemory
                self.node.qmemory.put(qubit, positions=[self.mem_position])

                success_index = current_attempt
                print(f"[{ns.sim_time()}] Repeater {self.node.ID}: Latched photon at attempt {success_index}")

            if ev_expr.second_term.value:
                if success_index is None:
                    success_index = -1

                msg = ns.components.Message(items = ["END", success_index])
                self.node_cport.tx_output(msg)

                yield self.await_port_input(self.node_cport)

                recv_msg = self.node_cport.rx_input()
                assert recv_msg.items[0] == "END"
                other_success_index = recv_msg.items[1]

                if success_index != -1 and success_index == other_success_index:
                    print(f"[{ns.sim_time()}] Repeater {self.node.ID}: Entanglement generation successful"
                            f" at attempt {success_index}")
                    
                    # I'm telling an upper layer protocol that in the quantum memory is present the entangled qubit
                    self.send_signal(self.ENTANGLED_SIGNAL, result = None)

                    # If we don't disable it the EPS continues to generate events, so the simulation does not end
                    if self.connection is not None:
                        self.connection.subcomponents["EPS"].status = ns.components.SourceStatus.OFF

                    return 
                else: 
                    start_time = ns.sim_time()
                    t_total_attempts = self.K_attempts * self.t_clock + ns.sim_time() + 5
                    success_index = None
                    # we must free the quantum memory slot otherwise the new qubit cannot be inserted
                    if 0 in self.node.qmemory.used_positions:
                        self.node.qmemory.pop(positions=[self.mem_position])
