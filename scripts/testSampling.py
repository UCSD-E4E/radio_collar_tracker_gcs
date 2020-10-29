import numpy as np

class pingTester:
    def __init__(self):

        pings = [[12345, 12345, 30, 3], 
                 [12345, 12345, 30, 7],
                 [12340, 12350, 30, 5],
                 [12343, 12346, 90, 4], 
                 [45678, 45678, 90, 4],
                 [45674, 45678, 90, 4],
                 [45678, 45674, 90, 4],
                 [45674, 45674, 23, 9]]
        self.currInd = 0
        self.indSkip = None
        newPings = self.resamplePings(pings)

        print(pings)
        print(newPings)

    def resamplePings(self, pings):
            pings = np.array(pings)
            pingCopy = None
            currInd = 0
            indSkip = np.array([])
            for ping in pings:
                if (currInd in indSkip):
                    currInd = currInd + 1
                    continue
                rad = 6
                ind = np.where((pings[:,0] < ping[0] + rad) & (pings[:,0] > ping[0] - rad) & (pings[:,1] < ping[1] + rad) & (pings[:,1] > ping[1]-rad))
                indSkip = np.append(indSkip, ind[0])
                
                currInd = currInd + 1
                if len(ind[0]) > 1:
                    newArr = None
                    for i in ind[0]:
                        if newArr is None:  
                            newArr = np.array([pings[i]])
                        else:     
                            newArr = np.vstack((newArr, [pings[i]]))
                    newArr = np.vstack((newArr, [ping]))
                    x = np.mean(newArr[:, 0])
                    y = np.mean(newArr[:, 1])
                    alt = np.mean(newArr[:, 2])
                    power = np.mean(newArr[:, 3])
                    #pings = np.delete(pings, ind[0], 0)
                    #pings = np.vstack((pings, [[x, y, alt, power]]))
                    if pingCopy is None:
                        pingCopy = np.array([[x, y, alt, power]])
                    else:
                        pingCopy = np.vstack((pingCopy, [[x, y, alt, power]]))
                else:
                    if pingCopy is None:
                        pingCopy = np.array([ping])
                    else:
                        pingCopy = np.vstack((pingCopy, [ping]))
            return pingCopy

i = pingTester()

