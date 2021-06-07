import sys
import os
sys.path.insert(0, os.getcwd())

import time

import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
import yaml
import os
from tqdm import tqdm

from fusions.robotics.sensor_fusion import SensorFusionSelfSupervised
from unimodals.robotics.encoders import (
    ProprioEncoder, ForceEncoder, ImageEncoder, DepthEncoder, ActionEncoder,
)
from unimodals.robotics.decoders import ContactDecoder
from training_structures.Simple_Late_Fusion import train, test
from robotics_utils import set_seeds

from datasets.robotics.data_loader_robust import get_data
from robustness.all_in_one import general_train, general_test
from torch.utils.data import DataLoader
from torch.utils.data.sampler import SubsetRandomSampler
from torchvision import transforms
from private_test_scripts.all_in_one import all_in_one_train

class selfsupervised:
    def __init__(self, configs):

        # ------------------------
        # Sets seed and cuda
        # ------------------------
        use_cuda = True

        self.configs = configs
        self.device = torch.device("cuda" if use_cuda else "cpu")

        set_seeds(configs["seed"], use_cuda)

        self.encoders = [
            ImageEncoder(configs['zdim'], alpha=configs['vision']),
            ForceEncoder(configs['zdim'], alpha=configs['force']),
            ProprioEncoder(configs['zdim'], alpha=configs['proprio']),
            DepthEncoder(configs['zdim'], alpha=configs['depth']),
            ActionEncoder(configs['action_dim']),
        ]
        self.fusion = SensorFusionSelfSupervised(
            device=self.device,
            encoder=configs["encoder"],
            deterministic=configs["deterministic"],
            z_dim=configs["zdim"],
        ).to(self.device)
        self.head = ContactDecoder(z_dim=configs["zdim"], deterministic=configs["deterministic"],head=4)
        

        self.optimtype = optim.Adam

        # losses
        self.loss_contact_next = nn.BCEWithLogitsLoss()

        self.train_loader, self.val_loader, self.test_loader = get_data(self.device, self.configs,output='ee_yaw_next')

    def train(self):
        print(len(self.train_loader.dataset), len(self.val_loader.dataset))
        with open('train_dataset.txt', 'w') as f:
            for x in self.train_loader.dataset.dataset_path:
                f.write(f'{x}\n')
        with open('val_dataset.txt', 'w') as f:
            for x in self.val_loader.dataset.dataset_path:
                f.write(f'{x}\n')
        def trainprocess(filename):
            train(self.encoders, self.fusion, self.head,
              self.train_loader, self.val_loader,
              50,task='regression',
              optimtype=self.optimtype, save=filename,
              lr=self.configs['lr'],criterion=torch.nn.MSELoss(),validtime=True)
        self.filename = general_train(trainprocess, 'robotics_trained-pred')
    
    def test(self):
        def testprocess(model, testdata):
            return test(model, testdata, criterion=torch.nn.MSELoss(), task='regression')
        general_test(testprocess, self.filename, self.test_loader)

with open('examples/robotics/training_default.yaml') as f:
    configs = yaml.load(f)


x = selfsupervised(configs)
x.train()
x.test()
