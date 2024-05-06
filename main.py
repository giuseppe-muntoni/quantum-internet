import math
from ent_swapping import EntSwapping
from ms_protocol import get_EPS_connection
import netsquid as ns
from purification import PurificationProtocol
from node import NetNode

def get_network(link_length, p_lr, p_m, t_clock):
    # create the network
    net = ns.nodes.Network("Quantum Repeater Network")
    
    # create the repeaters
    l_end_node = NetNode(ID = 1, name = "L_node")
    repeater = NetNode(ID = 2, name = "Repeater")
    r_end_node = NetNode(ID = 3, name = "R_node")

    # add the repeaters and connections to the network
    net.add_node(l_end_node)
    net.add_node(repeater)
    net.add_node(r_end_node)

    # create the classical connection
    channel_l_to_repeater = ns.components.ClassicalChannel("channel_l_to_repeater", length = link_length,
                                                           models = {"delay_model": ns.components.models.FibreDelayModel()})
    channel_repeater_to_l = ns.components.ClassicalChannel("channel_repeater_to_l", length = link_length,
                                                           models = {"delay_model": ns.components.models.FibreDelayModel()})
    
    classical_conn_l_repeater = ns.nodes.DirectConnection("classical_conn_l_repater", channel_l_to_repeater, channel_repeater_to_l)

    net.add_connection(node1 = l_end_node, node2 = repeater, connection = classical_conn_l_repeater,
                       port_name_node1 = "c0", port_name_node2 = "c0", label = "classical_conn_l_repeater")
    
    channel_repeater_to_r = ns.components.ClassicalChannel("channel_repeater_to_r", length = link_length,
                                                           models = {"delay_model": ns.components.models.FibreDelayModel()})
    channel_r_to_repeater = ns.components.ClassicalChannel("channel_r_to_repeater", length = link_length,
                                                           models = {"delay_model": ns.components.models.FibreDelayModel()})
    
    classical_conn_r_repeater = ns.nodes.DirectConnection("classical_conn_r_repater", channel_repeater_to_r, channel_r_to_repeater)

    net.add_connection(node1 = repeater, node2 = r_end_node, connection = classical_conn_r_repeater,
                       port_name_node1 = "c1", port_name_node2 = "c0", label = "classical_conn_r_repeater")
    
    # create the EPS connection
    eps_conn_l_repeater = get_EPS_connection(t_clock = t_clock, p_m = p_m, p_lr = p_lr, length = link_length)
    net.add_connection(node1 = l_end_node, node2 = repeater, connection = eps_conn_l_repeater,
                       port_name_node1 = "q0", port_name_node2 = "q0", label = "eps_conn_l_repeater")
    
    eps_conn_r_repeater = get_EPS_connection(t_clock = t_clock, p_m = p_m, p_lr = p_lr, length = link_length)
    net.add_connection(node1 = repeater, node2 = r_end_node, connection = eps_conn_r_repeater,
                       port_name_node1 = "q1", port_name_node2 = "q0", label = "eps_conn_r_repeater")
    
    K_attempts = math.ceil((1/p_m*p_lr))

    purif_protocol_l = PurificationProtocol(node = l_end_node, name = "PP_l", K_attempts = K_attempts, t_clock = t_clock,
                                           link_length = link_length, connection = eps_conn_l_repeater, nic_index = 0)
    
    purif_protocol_rep_1 = PurificationProtocol(node = repeater, name = "PP_rep_1", K_attempts = K_attempts, t_clock = t_clock,
                                           link_length = link_length, connection = None, nic_index = 0)
    
    purif_protocol_rep_2 = PurificationProtocol(node = repeater, name = "PP_rep_2", K_attempts = K_attempts, t_clock = t_clock,
                                           link_length = link_length, connection = eps_conn_r_repeater, nic_index = 1)
    
    purif_protocol_r = PurificationProtocol(node = r_end_node, name = "PP_r", K_attempts = K_attempts, t_clock = t_clock,
                                           link_length = link_length, connection = None, nic_index = 0)

    ent_swapping_repeater = EntSwapping(node=repeater, 
                                        purif_to_wait=[purif_protocol_rep_1, purif_protocol_rep_2],
                                        name="ent_swapping_repeater",
                                        is_left=True)
    
    ent_swapping_r_node = EntSwapping(node=r_end_node,
                                      purif_to_wait=[purif_protocol_r],
                                      name="ent_swapping_r_node",
                                      is_left=False)
    
    ent_swapping_repeater.set_swap_to_wait(ent_swapping_r_node)
    ent_swapping_r_node.set_swap_to_wait(ent_swapping_repeater)
    
    purif_protocol_l.start()
    ent_swapping_repeater.start_subprotocols()
    ent_swapping_r_node.start_subprotocols()
    ent_swapping_repeater.start()
    ent_swapping_r_node.start()

    return net

if __name__ == '__main__':
    # to represent mixed states
    ns.set_qstate_formalism(ns.QFormalism.DM)
    net = get_network(link_length = 30, p_lr = 0.9, p_m = 0.02, t_clock = 10)
    ns.sim_run()