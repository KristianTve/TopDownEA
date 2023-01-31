import pickle
import sys

import neat
import visualize
from mlagents_envs.environment import UnityEnvironment as UE
from mlagents_envs.base_env import ActionTuple  # Creating a compatible action
import numpy as np
import atexit

sim_1_agent = False
built_game = False
load_from_checkpoint = True
checkpoint = "checkpoints/NEAT-checkpoint-5585"
show_prints = True

if built_game:
    env = UE(seed=1, side_channels=[], file_name="Builds/5ENVSIMPLE/DodgeBallEnv.exe",
             additional_args=['--num-envs', '5'])
else:
    env = UE(seed=1, side_channels=[])

env.reset()  # Resets the environment ready for the next simulation
behavior_name_purple = list(env.behavior_specs)[0]
if len(list(env.behavior_specs)) > 1:
    behavior_name_blue = list(env.behavior_specs)[1]
    spec_blue = env.behavior_specs[behavior_name_blue]

spec_purple = env.behavior_specs[behavior_name_purple]

generation = 0

if show_prints:
    print(f"Name of the behavior : {behavior_name_purple}")
    print("Number of observations : ", len(spec_purple.observation_specs))
    print(spec_purple.observation_specs[0].observation_type)

    if len(list(env.behavior_specs)) > 1:
        print(f"Name of the behavior for players : {behavior_name_blue}")
        print("Number of observations : ", len(spec_blue.observation_specs))
        print(spec_blue.observation_specs[0].observation_type)


# Handles the exit by closing the unity environment to avoid _communicator errors.
def exit_handler():
    print("EXITING")
    env.close()


atexit.register(exit_handler)


def select_team(agent, purple_obj, blue_obj):
    """
    Returns the corresponding object to which team the agent id is in.
    """
    decision_steps_purple, terminal_steps_purple = env.get_steps(behavior_name_purple)
    decision_steps_blue, terminal_steps_blue = env.get_steps(behavior_name_blue)
    if agent in decision_steps_purple:  # Purple agent
        return purple_obj
    elif agent in decision_steps_blue:  # Blue agent
        return blue_obj
    else:
        if (len(decision_steps_blue) + len(decision_steps_purple)) == 0:
            return None  # Both teams are empty
        else:
            print("\nERROR, AGENT NOT ASSIGNED TO ANY TEAM")
            print("Blue Team: " + str(len(decision_steps_blue)))
            print("Purple Team: " + str(len(decision_steps_purple)))
            exit()


def run_agent(genomes, cfg):
    """
    Population size is configured as 12 to suit the training environment!
    :param genomes: All the genomes in the current generation.
    :param cfg: Configuration file
    :return: Best genome from generation.
    """
    # Decision Steps is a list of all agents requesting a decision
    # Terminal steps is all agents that has reached a terminal state (finished)
    decision_steps_purple, terminal_steps_purple = env.get_steps(behavior_name_purple)
    decision_steps_blue, terminal_steps_blue = env.get_steps(behavior_name_blue)
    # print(list(decision_steps_blue))
    # print(list(decision_steps_purple))
    # print("Genomes: " + str(len(genomes)))
    print_buffer = ""
    # TODO Implement a option to run a given neural network for all agents of one team, of which learning is disabled.
    # TODO But that requires only 12 players on one team.
    # Empty array to save all the neural networks for all agents on both teams
    policies = []

    # Initialize the neural networks for each genome.
    for i, g in genomes:
        # Each agent has their own genome which denotes their phenotype
        # Genomes consists of properties:
        # Key (ID)
        # Fitness (score)
        # Nodes and connections
        # "i" starts at 1
        policy = neat.nn.FeedForwardNetwork.create(g, cfg)
        policies.append(policy)
        g.fitness = 0

    global generation
    generation += 1
    done = False  # For the tracked_agent
    total_reward = 0

    # Agents:
    agent_count_purple = len(decision_steps_purple.agent_id)  # 12
    agent_count_blue = len(decision_steps_blue.agent_id)  # 12
    agent_count = agent_count_purple + agent_count_blue  # 24

    # for i in range(6):  # Which observation is the one we dont want
    #    decision_steps_nn = select_team(0, decision_steps_purple, decision_steps_blue)
    #    if decision_steps_nn[0].obs[i].shape == (3, 8):
    #        print("Obs: "+str(i)+" is other agent obs")

    while not done:
        # Store actions for each agent with 5 actions per agent (3 continuous and 2 discrete)
        actions = np.zeros(shape=(agent_count, 5))  # 23 in size because of the agent IDs going up to 22.

        # Concatenate all the observation data BESIDES obs number 3 (OtherAgentsData)
        nn_input = np.zeros(shape=(agent_count, 364))  # 23 in size because of the agent IDs going up to 22.

        for agent in range(agent_count):  # Collect observations from the agents requesting input
            decision_steps_nn = select_team(agent, decision_steps_purple, decision_steps_blue)
            nn_input[agent] = np.concatenate((decision_steps_nn[agent].obs[0],
                                              decision_steps_nn[agent].obs[1],
                                              decision_steps_nn[agent].obs[3],
                                              decision_steps_nn[agent].obs[4],
                                              decision_steps_nn[agent].obs[5]))

        # Checks if the
        if (len(decision_steps_purple) > 0) and (len(decision_steps_blue) > 0):  # More steps to take?
            for agent_index in range(agent_count):  # Iterates through all the agent indexes
                if (agent_index in decision_steps_purple) or (agent_index in decision_steps_blue):  # Is agent ready?
                    action = policies[agent_index].activate(nn_input[agent_index])  # FPass for purple action
                    actions[agent_index] = action  # Save action in array of actions

        # Clip discrete values to 0 or 1
        for agent in range(agent_count):
            actions[agent, 3] = 1 if actions[agent, 3] > 0 else 0  # Shoot
            actions[agent, 4] = 1 if actions[agent, 4] > 0 else 0  # DASH

        # Set actions for each agent (convert from ndarray to ActionTuple)
        if len(decision_steps_purple.agent_id) != 0 and len(decision_steps_blue.agent_id) != 0:
            for agent in range(agent_count):
                # Creating an action tuple
                continuous_actions = [actions[agent, 0:3]]
                discrete_actions = [actions[agent, 3:5]]
                action_tuple = ActionTuple(discrete=np.array(discrete_actions), continuous=np.array(continuous_actions))

                # Applying the action to respective agents on both teams
                behavior_name = select_team(agent, purple_obj=behavior_name_purple, blue_obj=behavior_name_blue)
                env.set_action_for_agent(behavior_name=behavior_name, agent_id=agent, action=action_tuple)

        # Move the simulation forward
        env.step()

        # Get the new simulation results
        decision_steps_purple, terminal_steps_purple = env.get_steps(behavior_name_purple)
        decision_steps_blue, terminal_steps_blue = env.get_steps(behavior_name_blue)

        # Collect reward
        reward = 0
        for agent_index in range(agent_count):
            decision_steps = select_team(agent_index, decision_steps_purple, decision_steps_blue)
            terminal_steps = select_team(agent_index, terminal_steps_purple, terminal_steps_blue)

            if decision_steps or terminal_steps:  # As long as the game is not quit
                if agent_index in decision_steps:  # The agent requested a decision
                    reward += decision_steps[agent_index].reward
                elif agent_index in terminal_steps:  # The agent is terminated
                    reward += terminal_steps[agent_index].reward

                genomes[agent_index][1].fitness += reward
                total_reward += reward  # Testing purposes (console logging)

        # When whole teams are eliminated, end the generation.
        if len(decision_steps_blue) == 0 or len(decision_steps_purple) == 0:
            print(".")  # Fix print last status before things are reset
            done = True

        # Reward status
        sys.stdout.write("\rCollective reward: %d | Blue left: %d | Purple left: %d" % (total_reward,
                                                                                        len(decision_steps_blue),
                                                                                        len(decision_steps_purple)))
        sys.stdout.flush()

    # Clean the environment for a new generation.
    env.reset()
    print("\nFinished generation")


def run_agent_sim(genome, cfg):
    """
    Population size is configured as 12 to suit the training environment!
    :param genome: The genome in the current generation.
    :param cfg: Configuration file
    :return: Best genome from generation.
    """
    for gen in range(50):
        # Decision Steps is a list of all agents requesting a decision
        # Terminal steps is all agents that has reached a terminal state (finished)
        decision_steps, terminal_steps = env.get_steps(behavior_name_purple)
        policy = neat.nn.FeedForwardNetwork.create(genome, cfg)

        global generation
        generation += 1
        done = False  # For the tracked_agent

        # Agents:
        agent_count = len(decision_steps.agent_id)  # 12

        while not done:
            # Concatenate all the observation data BESIDES obs number 3 (OtherAgentsData)
            nn_input = np.concatenate((decision_steps[0].obs[0],
                                       decision_steps[0].obs[1],
                                       decision_steps[0].obs[3],
                                       decision_steps[0].obs[4],
                                       decision_steps[0].obs[5]))

            action = np.zeros(shape=364)  # Init
            # Checks if the
            if len(decision_steps) > 0:  # More steps to take?
                if 0 in decision_steps:
                    action = policy.activate(nn_input)  # FPass for purple action

            # Clip discrete values to 0 or 1
            for agent in range(agent_count):
                action[3] = 1 if action[3] > 0 else 0  # Shoot
                action[4] = 1 if action[4] > 0 else 0  # DASH

            # Set actions for each agent (convert from ndarray to ActionTuple)
            if len(decision_steps.agent_id) != 0:
                # Creating an action tuple
                continuous_actions = [action[0:3]]
                discrete_actions = [action[3:5]]
                action_tuple = ActionTuple(discrete=np.array(discrete_actions), continuous=np.array(continuous_actions))

                # Applying the action
                env.set_action_for_agent(behavior_name=behavior_name_purple, agent_id=0, action=action_tuple)

            # Move the simulation forward
            env.step()

            decision_steps, terminal_steps = env.get_steps(behavior_name_purple)

            # When whole teams are eliminated, end the generation.
            if len(decision_steps) == 0:
                done = True

        # Clean the environment for a new generation.
        env.reset()


if __name__ == "__main__":
    # Set configuration file
    config_path = "./config"
    config = neat.config.Config(neat.DefaultGenome, neat.DefaultReproduction,
                                neat.DefaultSpeciesSet, neat.DefaultStagnation, config_path)
    if not sim_1_agent:
        # Create core evolution algorithm class
        if load_from_checkpoint:  # Load from checkpoint
            p = neat.Checkpointer.restore_checkpoint(checkpoint)
            print("LOADED FROM CHECKPOINT")
        else:  # Or generate new initial population
            p = neat.Population(config)

        # For saving checkpoints during training
        p.add_reporter(neat.Checkpointer(generation_interval=25, filename_prefix='checkpoints/NEAT-checkpoint-'))

        # Add reporter for fancy statistical result
        p.add_reporter(neat.StdOutReporter(True))
        stats = neat.StatisticsReporter()
        p.add_reporter(stats)

        # Run NEAT
        best_genome = p.run(run_agent, 500)

        # Save best genome.
        with open('result/best_genome.pkl', 'wb') as f:
            pickle.dump(best_genome, f)

        print(best_genome)

        visualize.plot_stats(stats, view=True, filename="result/feedforward-fitness.svg")
        visualize.plot_species(stats, view=True, filename="result/feedforward-speciation.svg")

        node_names = {-1: 'x', -2: 'dx', -3: 'theta', -4: 'dtheta', 0: 'control'}
        visualize.draw_net(config, best_genome, True, node_names=node_names)

        visualize.draw_net(config, best_genome, view=True, node_names=node_names,
                           filename="result/best_genome.gv")
        visualize.draw_net(config, best_genome, view=True, node_names=node_names,
                           filename="result/best_genome-enabled.gv", show_disabled=False)
        visualize.draw_net(config, best_genome, view=True, node_names=node_names,
                           filename="result/best_genome-enabled-pruned.gv", show_disabled=False, prune_unused=True)

    else:
        with open('result/best_genome.pkl', "rb") as f:
            genome = pickle.load(f)
            print(genome)

        run_agent_sim(genome, config)

