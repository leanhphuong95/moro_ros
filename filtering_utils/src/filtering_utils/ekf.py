#!/usr/bin/env python
import numpy as np
import math
from tf.transformations import euler_from_quaternion
from nav_msgs.msg import Odometry
import rospy

class EKF:
    def __init__(self, state_vector_size, control_size, measurement_size):
        self.state_vector = np.zeros((state_vector_size, 1))
        self.cov_matrix = 1000. * np.identity(state_vector_size)
        self.q = np.zeros((control_size, control_size))
        self.R = np.zeros((measurement_size, measurement_size))
        self.motion_j_state = np.zeros((state_vector_size, state_vector_size))
        self.motion_j_noise = np.zeros((state_vector_size, control_size))
        self.obs_j_state = np.zeros((measurement_size, state_vector_size))
        self.Q = np.zeros((state_vector_size, state_vector_size))
        self.beacons = {1:[7.3, 3.0], 2:[1,1],3:[9,9],4:[1,8],5:[5.8,8]}
        #
        self.v_sigma = [] # for sampling sigma
        self.w_sigma = [] # for sampling sigma
        self.prev_time_stamp = 0 # keeping the last time stamp
        self.initialized = False #!
        from nav_msgs.msg import Odometry
        self.gt = rospy.Subscriber('base_pose_ground_truth', Odometry, self.initialize_state_vector) # Initializing state_vector with ground truth
        #
    def initialize_state_vector(self, msg): # Function for initializing state_vector
        #print(msg)
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        theta = euler_from_quaternion([msg.pose.pose.orientation.x,msg.pose.pose.orientation.y,msg.pose.pose.orientation.z,msg.pose.pose.orientation.w])[2]
        self.state_vector[0] = x
        self.state_vector[1] = y
        self.state_vector[2] = theta
        self.gt.unregister() # unregister subscriber. Function is implemented only once.


    def predict(self, odometry): # odometry added by me
        #TODO determine q-matrix

        # Get v,w from odometry msg
        w = odometry.twist.twist.angular.z
        v = odometry.twist.twist.linear.x
        self.dt = (odometry.header.stamp.secs + odometry.header.stamp.nsecs*(10**-9))-self.prev_time_stamp
        #
        # get timestamp
        self.prev_time_stamp = odometry.header.stamp.secs + odometry.header.stamp.nsecs*(10**-9)
        #print('Seconds gone is', self.dt)
        #
        # form internal control vector
        self.control = [v,w]
        #
        # determine q-matrix aka process noise
        self.q = np.array(([0.004, 0],[0,0.001])) # FOR TEST PURPOSES
        #
        # Call functions
        self.propagate_state()
        self.calculate_cov()

    def update(self, msg):
        pass
        # Suppose we see only one beacon
        #info = msg.markers

        #print(info[0].ids[0])
        #self.cur_id = info[0].ids[0]
        #print(self.beacons[self.cur_id])    
        #self.observation_jacobian_state_vector()
        #floor = self.cov_matrix.dot(self.obs_j_state.transpose())
        #bottom = np.linalg.inv(self.obs_j_state.dot(self.cov_matrix).dot(self.obs_j_state.transpose()) + np.ones(2))
        #self.K = floor.dot(bottom)
            #print(self.beacons[cur_id])
            # jacobian is 2x3
            
            # one more comment
            #x = info[0].pose.position.x #info[0].ids
            #y = info[0].pose.position.y
            #z = info[0].pose.orientation.z
            #w = info[0].pose.orientation.w
            #angles = euler_from_quaternion([x,y,z,w])
            #print(math.degrees(angles[0]), math.degrees(angles[1]),math.degrees(angles[2]))
        #pass

    def propagate_state(self):
        #print(self.state_vector[1])
        if self.control[1] == 0:
            term = self.control[0]
            x = self.state_vector[0] + (term)*np.cos(self.state_vector[2]) # my
            y = self.state_vector[1] - (term)*np.sin(self.state_vector[2]) # my
            theta = self.state_vector[2] # TODO python wrapping: theta must be between -pi/2; pi/2
        else:
            term = self.control[0]/self.control[1]
            x = self.state_vector[0] + (term)*np.sin(self.state_vector[2] + self.control[1]) # my
            y = self.state_vector[1] - (term)*np.cos(self.state_vector[2] + self.control[1]) # my
            theta = self.state_vector[2] + self.control[1] # TODO python wrapping: theta must be between -pi/2; pi/2
        #print("Theta is",theta, "Unwrapped theta is", np.unwrap(np.angle(theta), discont=np.pi/2))
        self.state_vector = np.array([x,y,theta])
        self.motion_jacobian_state_vector()
        self.motion_jacobian_noise_components()
        #print(self.state_vector)
        #pass


    def measurement_model(self):
        #FIXME get properly done
        x = self.state_vector[0]
        y = self.state_vector[1]
        theta = self.state_vector[2]
        px = self.cur_id[0]
        py = self.cur_id[1]

        r = np.sqrt((px-x)**2 + (py-y)**2)      #Distance
        phi = np.arctan2(py-y, px-x) - theta    #Bearing

        Mx = np.array([[r],[phi]])              



    def calculate_cov(self): # Original multiplications was changed to "np.dot"-notation
        #self.Q = self.motion_j_noise * self.q * motion_j_noise.transpose() # original
        self.Q = self.motion_j_noise.dot(self.q).dot(self.motion_j_noise.transpose())
        #self.cov_matrix = self.motion_j_state * self.cov_matrix * \
        #    self.motion_j_state.transpose() + self.Q #original
        self.cov_matrix = self.motion_j_state.dot(self.cov_matrix).dot(self.motion_j_state.transpose()) + self.Q
        print(self.cov_matrix)

    def motion_jacobian_state_vector(self): # trailing zeros!
        #FIXME correct derivatives and add dt to the equations
        #print("Entry is", self.state_vector[2])
        if self.control[1] != 0:
            term = self.control[0]/self.control[1]
            row1term3 = term*np.cos(self.state_vector[2] + self.control[1]*self.dt)
            row2term2 = term*np.sin(self.state_vector[2] + self.control[1]*self.dt)
        else:
            row1term3 = -self.control[0]*np.sin(self.state_vector[2] + self.dt)
            row2term2 = -self.control[0]*np.cos(self.state_vector[2] + self.dt)
        self.motion_j_state = np.array(([1,0,row1term3],[0,1,row2term2],[0,0,1]))
        #print(self.motion_j_state) # 
        # self.motion_j_state
        pass

    def motion_jacobian_noise_components(self): # trailing zeros!
        # TO DO
        #print(self.state_vector[1])
        if self.control[1] != 0: # if angular velocity is not zero
            row1term1 = np.sin(self.state_vector[2] + self.control[1]*self.dt)/self.control[1] # check
            
            row1term2 = (-np.sin(self.state_vector[2] + self.control[1]*self.dt) + self.control[1]*self.dt*np.cos(self.control[1]*self.dt))/(self.control[1]**2) # check

            row2term1 = -np.cos(self.state_vector[2] + self.control[1]*self.dt) # check

            tempterm = self.state_vector[2] + self.control[1]*self.dt

            row2term2 = -self.control[0]*(-np.cos(tempterm) - self.control[1]*self.dt*np.sin(tempterm)) # check

            row3term1 = 0
            row3term2 = self.dt
        else:
            row1term1 = np.cos(self.state_vector[2] + self.dt)
            row1term2 = 0
            row2term1 = -np.sin(self.state_vector[2] + self.dt)
            row2term2 = 0
            row3term1 = 0
            row3term2 = self.state_vector[2] + 1 # dt = 1, possibly wrong
        self.motion_j_noise = np.array(([row1term1, row1term2],[row2term1,row2term2],[row3term1,row3term2]))
        #print(row1term1, row1term2, row2term1, row2term2, row3term1, row3term2)

        # self.motion_j_noise
        #pass

    def observation_jacobian_state_vector(self):
        # To DO
        self.cur_id = self.beacons[self.cur_id]
        #print(self.cur_id)
        row1term1 = (self.state_vector[0] - self.cur_id[0])/np.sqrt((self.state_vector[0] - self.cur_id[0])**2 + (self.state_vector[1] - self.cur_id[1])**2)
        row1term2 = (self.state_vector[1] - self.cur_id[1])/np.sqrt((self.state_vector[0] - self.cur_id[0])**2 + (self.state_vector[1] - self.cur_id[1])**2)
        row1term3 = 0
        row2term1 = (self.cur_id[1] - self.state_vector[1]) / ((self.cur_id[0] - self.state_vector[0])**2 + (self.cur_id[1] - self.state_vector[1])**2)
        row2term2 = (self.cur_id[0] - self.state_vector[0]) / ((self.cur_id[0] - self.state_vector[0])**2 + (self.cur_id[1] - self.state_vector[1])**2)
        row2term3 = -1
        self.obs_j_state = np.array(([row1term1, row1term2, row1term3],[row2term1,row2term2,row2term3]))
        #print(self.cov_matrix)
        # self.obs_j_state
        #pass

    def print_initials(self):
        print("Printing some values")
        #print(self.cov_matrix)
        #print("The initial stated is {}").format(self.state_vector)
        #print("The initial cov. matrix is {}").format(self.cov_matrix)