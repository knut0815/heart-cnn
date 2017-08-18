from __future__ import print_function

import numpy as np
import os
import sys
import tensorflow as tf
import tflearn
import sklearn
from numpy import interp
from sklearn.metrics import roc_curve, roc_auc_score
import scipy
import h5py
import datetime

# Import and preprocess data

if __name__ == "__main__":
    h5f = h5py.File("./data/all.h5", "r")
    h5f_test = h5py.File("./data/allTest.h5", "r")
    inData = h5f["inData"]
    inLabelsOH = h5f["inLabels"]
    inData_test = h5f_test["inData"]
    inLabelsOH_test = h5f_test["inLabels"]

    # Neural net (two-channel)
    sess = tf.InteractiveSession()
    tf.reset_default_graph()
    tflearn.initializations.normal()

    # Input layer:
    net = tflearn.layers.core.input_data(shape=[None,34,34,34,2])

    # First layer:
    net = tflearn.layers.conv.conv_3d(net, 32, [10,10,10],  activation="leaky_relu")
    net = tflearn.layers.conv.max_pool_3d(net, [2,2,2], strides=[2,2,2])

    # Second layer:
    net = tflearn.layers.conv.conv_3d(net, 64, [5,5,5],  activation="leaky_relu")
    net = tflearn.layers.conv.max_pool_3d(net, [2,2,2], strides=[2,2,2])

    # Third layer:
    net = tflearn.layers.conv.conv_3d(net, 128, [2,2,2], activation="leaky_relu") # This was added for CNN 2017-07-28

    # Fully connected layers
    net = tflearn.layers.core.fully_connected(net, 2048, activation="leaky_relu", regularizer="L2", weight_decay=0.01)
    #net = tflearn.layers.core.dropout(net, keep_prob=0.5)

    net = tflearn.layers.core.fully_connected(net, 1024, activation="leaky_relu", regularizer="L2", weight_decay=0.01)
    #net = tflearn.layers.core.dropout(net, keep_prob=0.5)

    net = tflearn.layers.core.fully_connected(net, 512, activation="leaky_relu", regularizer="L2", weight_decay=0.01)
    #net = tflearn.layers.core.dropout(net, keep_prob=0.5)

    # Output layer:
    net = tflearn.layers.core.fully_connected(net, 5, activation="softmax")

    net = tflearn.layers.estimator.regression(net, optimizer='adam', learning_rate=0.0001, loss='categorical_crossentropy')
    model = tflearn.DNN(net, tensorboard_verbose=0)

    # Train the model
    model.fit(inData, inLabelsOH, batch_size=100, n_epoch=30, show_metric=True, validation_set=0.1) # Need validation so I can see when learning stops
    dt = str(datetime.datetime.now().replace(second=0, microsecond=0).isoformat("_"))
    model.save("./models/"+dt+"_3d-2channel-fakedata-all.tflearn")

    # Retrieve indices of the different cubes and get the accuracies of each type
    inLabels_test = np.argwhere(inLabelsOH_test == 1)[:,1]
    mnorm = inLabels_test == 0
    accNorm = model.evaluate(inData_test[mnorm,...], inLabelsOH_test[mnorm,...], batch_size=100)
    mIs = inLabels_test == 1
    accIs = model.evaluate(inData_test[mIs,...], inLabelsOH_test[mIs,...], batch_size=100)
    mIn = inLabels_test == 2
    accIn = model.evaluate(inData_test[mIn,...], inLabelsOH_test[mIn,...], batch_size=100)
    mMi = inLabels_test == 3
    accMi = model.evaluate(inData_test[mMi,...], inLabelsOH_test[mMi], batch_size=100)
    mAr = inLabels_test == 4
    accAr = model.evaluate(inData_test[mAr], inLabelsOH_test[mAr], batch_size=100)

    # Get an ROC curve by lumping all of the unhealthy cubes together as ill
    predictednorm = model.predict(inData_test[mnorm,...][0][np.newaxis,...]) # Dirty hack to save memory
    for j in np.arange(1, inLabels_test[mnorm,...].shape[0]):
        predictednorm = np.append(predictednorm, model.predict(inData_test[mnorm,...][j][np.newaxis,...]), axis=0)

    predictedill = model.predict(inData_test[~mnorm,...][0][np.newaxis])
    for j in np.arange(1, inLabels_test[mnorm,...].shape[0]): # Have same amount of normal and abnormal data
        predictedill = np.append(predictedill, model.predict(inData_test[~mnorm,...][j][np.newaxis,...]), axis=0)

    # Mask array so that only healthy and wanted indices are shown. Normalise to binary.
    mill = inLabelsOH_test[~mnorm,...] == 1
    mill = mill[:inLabels_test[mnorm,...].shape[0]]
    mill[:,0] = True
    predBinaryIll = sklearn.preprocessing.normalize(predictedill[mill], norm="max", axis=1)

    # Mask array so that healthy and next largest indices are shown. If an index is larger than healthy use that and healthy. Normalise to binary.
    mhealth = inLabelsOH_test[mnorm,...] == 1
    sortedNormPred = np.argsort(predictednorm, axis==1)[::-1]
    for i in np.shape(sortedNormPred)[0]:
        if sortedNormPred[0] == 0:
            mhealth[i,sortedNormPred[1]] = True
        else:
            mhealth[i,sortedNormPred[0]] = True

    predBinaryHealth = sklearn.preprocessing.normalize(predictednorm[mhealth], norm="max", axis=1)

    predicted = np.concatenate((predBinaryIll,predBinaryHealth))
    binLabels = np.concatenate((np.ones(inLabels_test[mnorm,...].shape[0]),np.zeros(inLabels_test[mnorm,...].shape[0])))
    fpr, tpr, th = roc_curve(binLabels, predicted[:,1])
    auc = roc_auc_score(binLabels, predicted[:,1])

    acc = model.evaluate(inData_test, inLabelsOH_test, batch_size=100)
    print(accNorm,accIs,accIn,accMi,accAr,acc)
    savefileacc = "./logs/"+dt+"_3d-2channel-fakedata-acc_all.log"
    savefileroc = "./logs/"+dt+"_3d-2channel-fakedata-acc_all.log"
    np.savetxt(savefileacc, (accNorm,accIs,accIn,accMi,accAr,acc,auc), delimiter=",")
    np.savetxt(savefileroc, (fpr,tpr,th), delimiter=",")
    h5f.close()
    h5f_test.close()