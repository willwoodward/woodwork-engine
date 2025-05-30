class Classifier(nn.Module):
    def __init__(self):
        super(Classifier, self).__init__()

        conv_layer_sizes = [3, 3*8, 3*14, 3*24, 3*36]

        self.conv_layers = nn.Sequential(
            *[
                nn.Sequential(
                    self.conv_block(conv_layer_sizes[i], conv_layer_sizes[i], kernel_size=3, stride=1, padding=1, groups=3),
                    self.conv_block(conv_layer_sizes[i], conv_layer_sizes[i+1], kernel_size=4, stride=2, padding=1, groups=3),
                )
                for i in range(len(conv_layer_sizes)-1)
            ]
        )
        
        self.linear_layers = nn.Sequential(
            self.linear_layer(conv_layer_sizes[-1], 64),
            self.linear_layer(64, 64),
            nn.Linear(64, 20)
        )

        self.dropout = nn.Dropout(0.1)

    def conv_block(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1, groups=3):
        return nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, groups=groups),
            nn.BatchNorm2d(out_channels),
            nn.LeakyReLU()
        )
    
    def linear_layer(self, in_nodes, out_nodes):
        return nn.Sequential(
            nn.Linear(in_nodes, out_nodes),
            nn.BatchNorm1d(out_nodes),
            nn.ReLU()
        )
    
    def forward(self, x):
        x = self.conv_layers(x)
        x = self.linear_layers(x.view(x.size(0), -1))
        x = self.dropout(x)
        return x
