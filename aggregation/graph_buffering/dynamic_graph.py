import time

from aggregation.graph_buffering.abstract_dynamic_graph import AbstractDynamicGraph
from aggregation.graph_building.graph import RuanGraph
from aggregation.graph_building.graph_coloring import GraphColoration
from aggregation.graph_building.relations import RuanRelationsMap
from extraction import Tube
from utils.helpers import frame_intersect


class RuanDynamicGraph(AbstractDynamicGraph):
    def __init__(self, q=3, h=1, p=3):
        super(RuanDynamicGraph, self).__init__(q=q, h=h, p=p)
        self.current_starting_times = None  # the starting times for tubes in current graph (time step t)
        self.graph_coloration = None  # The coloring machine that helps to color the initial graph
        self.c_min = 0  # c_min value in Ruan et al. 2019 - available value for new tube stitching in

    def run_pipeline(self):
        """
        Pipeline using to update the graph through time steps.
        Combine with the method using potential collisions graph
        """
        # TODO: define tubes_buffer for further development for real-time
        while len(self.tubes_buffer):
            # Push a tube from buffer to process
            self.tubes_in_process.append(self.tubes_buffer[0])
            self.tubes_buffer = self.tubes_buffer[1:]

            # If the number of tubes gets up to p then a tube
            # will be selected and fused into synopsis video
            if len(self.tubes_in_process) >= self.p:
                if self.graph is None:
                    # Building the graph
                    relation_map = RuanRelationsMap(self.tubes_in_process)
                    self.graph = RuanGraph(self.tubes_in_process, relation_map)

                    # Color the initial graph and get the starting time of each tube
                    self.graph_coloration = GraphColoration(self.q)
                    self.graph = self.graph_coloration.color_graph(self.graph)
                    self.current_starting_times = self.graph_coloration.tube_starting_time(self.graph)
                else:
                    new_tube = self.tubes_in_process[-1]

                    # Remove the tube with minimum starting times
                    tube_del, removed_tag = self.removing()
                    # TODO: records the removed tube for stitching

                    # Update the value of c_min
                    self.c_min = max(self.c_min, tube_del.color)

                    # Update the graph
                    self.graph = self.updating(new_tube)

                    # Update the list of tubes in processing
                    self.tubes_in_process = self.graph.tubes
                    # TODO: record the final graph to stitch the rest tubes in synopsis video

    def removing(self):
        """
        Remove the tube with minimum starting time then stitch it to the output video
        """
        # Sort to get the tube with the minimum starting time to remove it
        tmp = sorted(self.current_starting_times.items(), key=lambda item: item[1])

        # Get the information of removed_tubes to stitch it to the video synopsis
        removed_tag, remove_starting_time = tmp[0]
        removed_tubes = [tube for tube in self.graph.tubes if tube.tag == removed_tag]

        # Update the list of rest tube in graph
        self.graph.tubes = [tube for tube in self.graph.tubes if tube.tag != removed_tag]
        return removed_tubes, remove_starting_time

    @staticmethod
    def get_color(tube: Tube, n):
        """
        Given the tube and a number n: index of frame start from 0
        return the appearance times of the nth frame of that tube
        """
        return tube.color + n

    def updating(self, new_tube):
        """
        Update the graph with new coming tube.
        Compare between two method adding and adjusting, choose the method that give
        better condensation.
        """
        tmp_graph1 = self.adding(new_tube)
        tmp_graph2 = self.adjusting(new_tube)

        
        return self.graph

    def adding(self, new_tube: Tube):
        """
        @@ hehehe @@ Adding method described by Ruan et al. 2019
        """
        # TODO: Define NC as a list or a dict? how to manage memory if number_of_collisions as a list
        # Try to place the new tube in the available graph
        c_tmp: int = 0
        for a_index, a_data in new_tube:
            for tube_in_process in self.graph.tubes:
                for b_index, b_data in enumerate(tube_in_process):
                    if frame_intersect(a_data, b_data):
                        c_tmp = self.get_color(tube_in_process, b_index) - a_index + 1
                    if c_tmp >= 0:
                        self.number_of_collisions[c_tmp] = self.number_of_collisions[c_tmp] + 1

        # Color the new tube based on the list of available places
        for color in range(self.c_min, len(self.number_of_collisions)):
            if self.number_of_collisions[color] <= self.h:
                new_tube.color = color

        # Add new tube to available graph to create new graph G(t+1)
        self.graph.tubes.append(new_tube)
        return self.graph

    def adjusting(self, new_tube: Tube):
        """
        Adjusting method described by Ruan et al. 2019
        """
        # Initialize a queue for adjusting
        queue = []

        # Put new tube at time location of c_min
        new_tube.color = self.c_min
        # Check if new_tube collide with tube in progress
        for potential_collide_tube in self.graph.tubes:
            is_collided_flag = False
            for a_data in new_tube:
                for b_data in potential_collide_tube:
                    # If new tube collides with potential_collide_tube
                    # remove the potential_collide_tube from graph the push it back into queue
                    if frame_intersect(a_data, b_data):
                        is_collided_flag = True
                        # In paper, authors described tube buffer as a queue,
                        # so i wonder if this could make chronological disorders
                        queue.append(potential_collide_tube)
                        self.graph.tubes = [tube for tube in self.graph.tubes if tube.tag != potential_collide_tube.tag]
                        break
                if is_collided_flag:
                    break

        # Add new tube to the available graph to create new graph G(t+1)
        self.graph.tubes.append(new_tube)

        # Add all the tubes in the queue into the graph again
        while len(queue):
            tube_in_queue = queue.pop(0)
            self.graph = self.adding(tube_in_queue)
        return self.graph
