''' Copyright (c) 2017 Roozbeh Sanaei and SUTD-MIT international design centre

Permission is hereby granted,  free of charge,  to any person obtaining a copy
of this software and associated documentation files (the "Software"),  to deal
in the Software without restriction,  including without limitation the rights
to use,  copy,  modify,  merge,  publish,  distribute,  sublicense,  and/or sell
copies of the Software,  and to permit persons to whom the Software is
furnished to do so,  subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS",  WITHOUT WARRANTY OF ANY KIND,  EXPRESS OR
%IMPLIED,  INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NON INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,  DAMAGES OR OTHER
LIABILITY,  WHETHER IN AN ACTION OF CONTRACT,  TORT OR OTHERWISE,  ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.'''

#In this code three different strategies has been used for clustering, clustermatrix and stochastic hill climbing strategy are employed

import csv
import numpy as np
import random
import math
from multiprocessing import Pool
from functools import partial
import sys
from tqdm import trange

def fix(seq):
    c = 0
    d = dict()
    n = len(seq)
    for i in range(0,n):
        if not(seq[i] in d.keys()):
            d[seq[i]] = c
            c = c + 1
        seq[i] = d[seq[i]]



def seq_2_size(seq):
    s = np.zeros(max(seq) + 1)
    for i in seq:
        s[i] = s[i] + 1
    return(s)

def seq_2_mat(seq):
    n = len(seq)
    m = max(seq)+1
    mat = np.zeros((m,n))
    mat[(seq,range(0,n))]=1
    return(mat)

def mat_2_seq(mat):
    seq = [np.nonzero(mat[:,i])[0][0] for i in range(mat.shape[1])]
    return (seq)


def cost(DSM,  cluster_matrix,  costs,  pow_cc,objectives):

    v = []
    if 1 in objectives:
        dsm_size = DSM.shape[0]
        io = np.dot(np.dot(cluster_matrix, DSM), cluster_matrix.transpose())
        ioi = io.diagonal()
        ios = np.sum(io)
        iois = np.sum(ioi)
        ioe = ios - iois
        io_extra = ioe * dsm_size
        v.append(io_extra)

    if 2 in objectives:
        cluster_size = np.sum(cluster_matrix, axis=1)
        cscc = np.power(cluster_size, pow_cc)
        io_intra = np.dot(ioi, cscc)
        v.append(io_intra)

    if 3 in objectives:
        number_of_modules = len(np.nonzero(cluster_size)[0])
        v.append(number_of_modules)

    return(v)




#remove empty clusters
def trim_clusters(clusters):
    cluster_size = np.sum(clusters, axis=1)
    empty_clusters = np.argwhere(cluster_size == 0)
    clusters = np.delete(clusters, empty_clusters, axis=0)
    cluster_size = np.delete(cluster_size,  empty_clusters)
    return [clusters, cluster_size]


#calculates cluster bid matrix
def Iplus_bid_matrix(  DSM,  Cluster_matrix,  pow_dep,  pow_bid,  cluster_size, constraints, fixed_elements):
    flag = np.zeros(Cluster_matrix.shape)
    flag[np.where(np.dot(Cluster_matrix, np.multiply((1-constraints), np.outer(np.transpose(1-fixed_elements),(1-fixed_elements))))==0)]=1
    exclude_itself = np.identity(DSM.shape[0])
    inputs = np.dot(Cluster_matrix,  DSM - exclude_itself)
    cluster_size_pow = np.power(cluster_size, pow_bid)
    cluster_bid = np.multiply(flag, np.divide(np.power(inputs,  pow_dep), cluster_size_pow[:,None]));
    return(cluster_bid)

#calculates cluster bid measuring degree of fitness between an element and a cluster
def Iplus_bid(elmt,  DSM,  cluster_seq,  pow_dep,  pow_bid,  cluster_size, constraints, fixed_elements):
    Cluster_matrix = seq_2_mat(cluster_seq)
    flag = np.zeros(Cluster_matrix.shape[0])
    flag[np.where(np.dot(Cluster_matrix, (1-(constraints[elmt, :]+fixed_elements)))==0)]=1
    exclude_itself = np.identity(DSM.shape[0])
    inputs = np.dot(Cluster_matrix,  DSM[:,  elmt] - exclude_itself[:,  elmt])
    cluster_bid = np.multiply(flag, np.divide(np.power(inputs,  pow_dep), np.power(cluster_size,  pow_bid)))
    cluster_bid[cluster_seq[elmt]] = 0
    return(cluster_bid)

#calculates cluster bid and only takes consttaints into account wiuthout estimating fitting
def Iplus_bid1(elmt,  DSM,  cluster_seq,  pow_dep,  pow_bid,  cluster_size, constraints, fixed_elements):
    Cluster_matrix = seq_2_mat(cluster_seq)
    flag = np.zeros(Cluster_matrix.shape[0])
    flag[np.where(np.dot(Cluster_matrix, (1-(constraints[elmt, :]+fixed_elements)))==0)]=1
    return(flag)

#read a series of float values from a file
def read_floats(file_name):
    file = open(file_name, 'r')
    contents = file.readlines()
    values = [float(value.rstrip('\n')) for value in contents]
    return  values


def rand():
    global rand_index
    global rands
    rand_index = rand_index + 1
    return(rands[rand_index-1])

#compute hash function of cluster matrix
def hash(x):
    return(np.dot(np.sum(x, axis=1), np.array(range(1, (len(x) + 1)))))

#move a randomly choosen elment based on cluster bid likelihood to a cluster choosen based based on clusterbid likelihood
def move1(available_elements,DSM,cluster_seq, constraints,pow_dep, pow_bid,fixed_elements,rand_bid):
    new_cluster_seq = None
    new_cluster_size = None
    cluster_bid = Iplus_bid_matrix( DSM, cluster_seq, pow_dep, pow_bid, seq_2_size(cluster_seq), constraints, fixed_elements)+0.00001
    cluster_bid = cluster_bid.flatten()
    prob = np.divide(cluster_bid,(np.sum(cluster_bid)))
    r = random.random()
    pick = np.where(np.add.accumulate(prob)>r)[0][0]
    my_idx = pick//len(cluster_seq)
    elmt = pick%len(cluster_seq)
    new_cluster_seq = cluster_seq.copy()
    new_cluster_seq[elmt] = my_idx
    fix(new_cluster_seq)
    return (new_cluster_seq)

#move a randomly choosen elment with uniform likelihood to a cluster choosen based on likelihood equal to cluster bid
def move2(available_elements,DSM,cluster_seq, constraints,pow_dep, pow_bid,fixed_elements,rand_bid):
    new_cluster_seq = None
    new_cluster_size = None
    elmt = available_elements[math.floor(random.random() * (len(available_elements) - 1))]
    cluster_bid = Iplus_bid(elmt, DSM, cluster_seq, pow_dep, pow_bid, seq_2_size(cluster_seq), constraints, fixed_elements)+0.0000001
    prob = np.divide(cluster_bid,(np.sum(cluster_bid)))
    my_idx = np.where(np.add.accumulate(prob)>random.random())[0][0]
    new_cluster_seq = cluster_seq.copy()
    new_cluster_seq[elmt] = my_idx
    fix(new_cluster_seq)
    return (new_cluster_seq)

#move a randomly choosen elment with uniform likelihood to a cluster choosen based on highest cluster bid
def move3(available_elements, DSM, cluster_seq, constraints, pow_dep, pow_bid, fixed_elements,rand_bid):
    n_affected_clusters = 0
    new_cluster_seq = None
    new_cluster_size = None
    elmt = available_elements[math.floor(random.random() * (len(available_elements) - 1))]
    cluster_bid = Iplus_bid(elmt, DSM, cluster_seq, pow_dep, pow_bid, seq_2_size(cluster_seq), constraints, fixed_elements)
    best_cluster_bid = np.amax(cluster_bid)
    second_best_cluster_bid = np.amax(np.multiply(best_cluster_bid != cluster_bid, cluster_bid))
    if (math.floor(random.random() * rand_bid) == 0):
        best_cluster_bid = second_best_cluster_bid
    affected_list = [i for i in range(len(cluster_bid)) if ((cluster_bid[i] == best_cluster_bid))]
    my_idx = affected_list[math.floor(random.random() * (len(affected_list) - 1))]
    new_cluster_seq =  cluster_seq.copy()
    new_cluster_seq[elmt] = my_idx
    fix(new_cluster_seq)
    return (new_cluster_seq)




def read_matrix_without_header(file):
    with open(file,  'r') as csvfile:
        file_contents = csv.reader(csvfile,  delimiter=',',  quotechar='"')
        extracted_matrix = [c[1:len(c)] for c in file_contents]
    extracted_matrix.pop(0)
    return (extracted_matrix)

def read_matrix_with_header(file):
    with open(file,  'r') as csvfile:
        file_contents = csv.reader(csvfile,  delimiter=',',  quotechar='"')
        extracted_matrix = [c[0:len(c)] for c in file_contents]
    return (extracted_matrix)





def print_cluster(c):
    for l in c:
            print(list(l.nonzero()[0]))

#stochastic hill climbing strategy
def cluster2(thread_index,DSM,data,constraints,fixed_modules,runs_per_thread,multi_objective,core_parameters,objectives):
    clusters = []
    clusters = [0 for i in range(0,runs_per_thread)]
    dsm_size = DSM.shape[0]
    fixed_elements = np.zeros(dsm_size)
    for module in fixed_modules:
        fixed_elements[module] = 1
    available_elements = (np.nonzero(1 - fixed_elements))[0]
    [pow_cc, pow_bid, pow_dep, rand_accept, rand_bid, number_of_iterations, stable_limit] = core_parameters

    for i in trange(runs_per_thread):
        if (multi_objective):
            p = i/runs_per_thread
        else:
            p = 0.5

        clusters[i] = np.random.randint(np.random.randint(dsm_size/4,3*dsm_size/4)+1, size=dsm_size ) + len(fixed_modules)


        for j in range(len(fixed_modules)):
            clusters[i][fixed_modules[j]] = j

        fix(clusters[i])


    for i in trange(runs_per_thread):
        if (multi_objective):
            p = i / runs_per_thread
        else:
            p = 0.5

        cst = cost(DSM, seq_2_mat(clusters[i]), data, pow_cc, objectives)
        total_costs[i] = p * cst[0] + (1 - p) * cst[1]

        stable = 0
        changed = 0

        while (stable < stable_limit):
            for k in range(number_of_iterations):
                accept1 = 0
                new_cluster_seq = move(available_elements, DSM, clusters[i], constraints,
                                                                     pow_dep, pow_bid, fixed_elements,
                                                                     rand_bid)

                c = cost(DSM, seq_2_mat(new_cluster_seq), data, pow_cc, objectives)
                new_total_cost = p * c[0] + (1 - p) * c[1]
                if ((new_total_cost <= total_cost) | (math.floor(rand_accept * random.random()) == 0)):
                    accept1 = 1

                if (accept1):
                    accept1 = 0
                    if (total_cost > new_total_cost):
                        total_cost = new_total_cost.copy()
                        clusters[i] = new_cluster_seq.copy()
                        changed = True
            if (changed):
                stable = 0
                changed = False
            else:
                stable = stable + 1

    return(clusters)


#evolutionary strategy
def cluster(thread_index,DSM,data,constraints,fixed_modules,runs_per_thread,multi_objective,core_parameters,objectives):
    move = move3
    clusters = []
    clusters = [0 for i in range(0,runs_per_thread)]
    new_clusters = [0 for i in range(0, runs_per_thread)]
    total_costs = [0 for i in range(0,runs_per_thread)]
    new_total_costs = [0 for i in range(0,runs_per_thread)]
    dsm_size = DSM.shape[0]
    fixed_elements = np.zeros(dsm_size)
    for module in fixed_modules:
        fixed_elements[module] = 1
    available_elements = (np.nonzero(1 - fixed_elements))[0]
    [pow_cc, pow_bid, pow_dep, rand_accept, rand_bid, number_of_iterations, stable_limit] = core_parameters

    p = 0.5

    for i in trange(runs_per_thread):


        clusters[i] = np.random.randint(np.random.randint(dsm_size/4,3*dsm_size/4)+1, size=dsm_size ) + len(fixed_modules)


        for j in range(len(fixed_modules)):
            clusters[i][fixed_modules[j]] = j

        fix(clusters[i])


    for i in trange(runs_per_thread):

        cst = cost(DSM, seq_2_mat(clusters[i]), data, pow_cc, objectives)
        total_costs[i] = p * cst[0] + (1 - p) * cst[1]

    for k in trange(5*number_of_iterations):

        indices = random.sample(range(0, runs_per_thread), runs_per_thread)


        for i in range(len(new_clusters)):
            new_clusters[i] = move(available_elements, DSM, clusters[i], constraints,
                                                                 pow_dep, pow_bid, fixed_elements,
                                                                 rand_bid)

            c = cost(DSM, seq_2_mat(new_clusters[i]), data, pow_cc, objectives)

            new_total_costs[i] = p * c[0] + (1 - p) * c[1]

        #if ((new_total_costs[i] <= total_costs[i]) | (math.floor(rand_accept * random.random()) == 0)):
        '''    if (new_total_costs[i] < total_costs[i]):
                total_costs[i] = new_total_costs[i]
                clusters[i] = new_clusters[i] '''


        clusters = clusters + new_clusters
        total_costs = total_costs + new_total_costs


        #prob = np.divide(total_costs, (np.sum(total_costs)))
        #indices = [np.where(np.add.accumulate(prob) > random.random())[0][0] for i in range(runs_per_thread)]
        #hash_values = [np.dot(cluster, range(0, len(cluster))) for cluster in clusters]

        #indices = np.argsort(total_costs)
        [_, indices] = np.unique(total_costs, return_index=True)

        #ndices = [i[0] for i in sorted(enumerate(total_costs), key=lambda x: x[1])]
        new_clusters = [clusters[i] for i in indices[0:runs_per_thread]]
        new_total_costs = [total_costs[i] for i in indices[0:runs_per_thread]]
        clusters = new_clusters.copy()
        total_costs = new_total_costs.copy()

    return clusters




def find_pareto_points(objective1,objective2,number_of_pareto_points):
    obj_1_min = np.min(objective1)
    obj_1_max = np.max(objective1)
    obj_1_offset = (obj_1_max - obj_1_min) / number_of_pareto_points
    obj_1_min_grid = np.arange(obj_1_min,obj_1_max,obj_1_offset)

    pareto = []
    for i in range(len(obj_1_min_grid)-1):
        indices = (np.where((obj_1_min_grid[i]<=objective1)&(objective1<obj_1_min_grid[i+1])))[0]
        if len(indices)>0:
            pareto.append(indices[np.argmin(objective2[indices])])
    return (pareto)




def read_parameters():

    #if parameters_filename is given as argument use it otherwise use a default microcontroller file
    try:
        parameters_filename = sys.argv[1]
    except:
        parameters_filename = 'examples/dust buster parameters.csv'

    # read parameters from parameter file
    parameters = [values[0] for values in read_matrix_without_header(parameters_filename)]
    # load DSM, constraints matrix and data matrix
    DSM = np.array(read_matrix_without_header(parameters[0])).astype(int)

    # set parameters as default values
    constraints = np.ones(DSM.shape)
    #constraints[18, 19] = 0
    #constraints[19, 18] = 0
    data = []
    core_parameters = [1, -2, 2, 2 * DSM.shape[0], 2 * DSM.shape[0], 2 * DSM.shape[0], 2]
    number_of_threads = 1
    runs_per_thread = 1000
    multi_objective = True


    #if any parameter is given in correct form use that value otherwise leave it as default
    try:
        constraints = np.array(read_matrix_without_header(parameters[1])).astype(int)
        data = np.array(read_matrix_without_header(parameters[2])).astype(float)
        core_parameters[0] = int(parameters[3])
        core_parameters[1] = int(parameters[4])
        core_parameters[2] = int(parameters[5])
        core_parameters[3] = int(parameters[6])
        core_parameters[4] = int(parameters[7])
        core_parameters[5] = int(parameters[8])
        core_parameters[6] = int(parameters[9])
        number_of_threads = int(parameters[10])
        runs_per_thread = int(parameters[11])
        if parameters[12] == 'False':
            multi_objective = False
    except:
        pass


    return [DSM,constraints,data,core_parameters,number_of_threads,runs_per_thread,multi_objective]

def convergence_population_plot(total_costs):
    points = [np.min(total_costs[0:i]) for i in range(10,len(total_costs))]
    import matplotlib.pyplot as plt
    plt.scatter(range(10,len(total_costs)), points, c='black')
    plt.show()

if __name__ == '__main__':



    [DSM, constraints, data, core_parameters, number_of_threads, runs_per_thread, multi_objective] = read_parameters()

    #fixed_modules = [[1,2],[3,4],[5,6,7]]
    fixed_modules = []


    #if more than number of threads is more than 1 use a process pool otherwise use a single thread
    if (number_of_threads > 1):
        with Pool(number_of_threads) as pool:
            clustering_results = pool.map(partial(cluster, DSM=DSM, data=data, constraints=constraints, fixed_modules=fixed_modules,
                                       runs_per_thread=runs_per_thread, multi_objective=multi_objective,
                                       core_parameters=core_parameters,objectives=[1,2]), range(number_of_threads))
    else:
        clustering_results = [
            cluster(0, DSM=DSM, data=data, constraints=constraints, fixed_modules=fixed_modules,
                    runs_per_thread=runs_per_thread,multi_objective=multi_objective,
                    core_parameters=core_parameters,objectives=[1,2])]

    clustering_sequences = np.concatenate(clustering_results, axis=0);


    cluster_costs = np.array([cost(DSM, seq_2_mat(clustering_sequence), data, 1,[1,2,3]) for clustering_sequence in clustering_sequences])

    total_costs = cluster_costs[:,0]+cluster_costs[:,1]
    #find cluster with minimum total cost prints it components and costs
    min_index = np.argmin(total_costs)
    print_cluster(seq_2_mat(clustering_sequences[min_index]))
    print('total cost:',0.5*cluster_costs[min_index][0]+0.5*cluster_costs[min_index][1],'extra cluster cost :',cluster_costs[min_index][0],'intra cluster cost :',cluster_costs[min_index][1],'number of modules :',cluster_costs[min_index][2])

    # find pareto frontier
    pareto1 = find_pareto_points(objective1=cluster_costs[:,0],objective2=cluster_costs[:,1],number_of_pareto_points=100)



    #convergence_population_plot(total_costs)

    # plot pareto frontier
    if multi_objective:
        import matplotlib.pyplot as plt
        plt.scatter(cluster_costs[:,0], cluster_costs[:,1],c = 'black')
        plt.scatter(cluster_costs[pareto1, 0], cluster_costs[pareto1, 1], c='red',marker = "o")
        plt.scatter(cluster_costs[min_index, 0], cluster_costs[min_index, 1], c='black',s=50)
        plt.xlabel('intra cluster cost')
        plt.ylabel('extra cluster cost')
        plt.show()