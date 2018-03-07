"""

   BiLSTM on I2b2 Assertion Status Classification

"""
from __future__ import print_function
import tensorflow as tf
from math import ceil


class AssertionModel:

    def __init__(self, seq_max_len, feat_size, n_classes):
        with tf.device('/gpu:0'):
            self.x = tf.placeholder("float", [None, seq_max_len, feat_size], 'x_input')
            self.y = tf.placeholder("float", [None, n_classes], 'y_output')
            # A placeholder for indicating each sentence length
            self.seqlen = tf.placeholder(tf.int32, [None], 'seq_len')
            self.n_classes = n_classes

    @staticmethod
    def fully_connected_layer(input_data, output_dim, activation_func=None):
        input_dim = int(input_data.get_shape()[1])
        W = tf.Variable(tf.random_normal([input_dim, output_dim]))
        b = tf.Variable(tf.random_normal([output_dim]))
        if activation_func:
            return activation_func(tf.matmul(input_data, W) + b)
        else:
            return tf.matmul(input_data, W) + b

    def add_bidirectional_lstm(self, dropout=0.25, n_hidden=30, num_layers=3):

        # TODO: check dimensions of 'x', (batch_size, n_steps, n_input)
        seq_max_len = self.x.get_shape()[1]

        for layer_num in range(1, num_layers + 1):
            # Define a lstm cell with tensorflow  -  Forward direction cell
            lstm_fw_cell = tf.nn.rnn_cell.BasicLSTMCell(n_hidden, forget_bias=1.0, name='fw' + str(layer_num))
            lstm_fw_cell = tf.nn.rnn_cell.DropoutWrapper(lstm_fw_cell, output_keep_prob=1.0 - dropout)

            # Backward direction cell
            lstm_bw_cell = tf.nn.rnn_cell.BasicLSTMCell(n_hidden, forget_bias=1.0, name='bw' + str(layer_num))
            lstm_bw_cell = tf.nn.rnn_cell.DropoutWrapper(lstm_bw_cell, output_keep_prob=1.0 - dropout)

            # Get lstm cell output, providing 'sequence_length' will perform dynamic
            # calculation.
            if layer_num is 1:
                input = self.x
            else:
                input = outputs
            outputs, _ = \
                tf.nn.bidirectional_dynamic_rnn(lstm_fw_cell, lstm_bw_cell,
                                                input, dtype=tf.float32,
                                                sequence_length=self.seqlen)

            # As we have Bi-LSTM, we have two output, which are not connected. So merge them
            # dim(outputs) == [batch_size, max_time, cell_fw.output_size] & [batch_size, max_time, cell_bw.output_size]
            outputs = tf.concat(axis=2, values=outputs)

        # Hack to build the indexing and retrieve the right output.
        batchSize = tf.shape(outputs)[0]

        # Start indices for each sample
        index = tf.range(0, batchSize) * seq_max_len + (self.seqlen - 1)

        # Index of the last output for the variable length sequence
        outputs = tf.gather(tf.reshape(outputs, [-1, n_hidden * 2]), index)

        # Linear activation, using outputs computed above
        self.bi_lstm = AssertionModel.fully_connected_layer(outputs, self.n_classes)

    def train(self, trainset, testset, epochs, batch_size=64, learning_rate=0.01, device='/cpu:0'):
        with tf.device(device):
            pred = self.bi_lstm

            # Define loss and optimizer
            cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=pred, labels=self.y))
            optimizer = tf.train.GradientDescentOptimizer(learning_rate=learning_rate).minimize(cost)

            # Initialize the variables (i.e. assign their default value)
            init = tf.global_variables_initializer()

        # Start training
        with tf.Session() as sess:
            # Run the initializer
            sess.run(init)

            # some debugging
            variable_names = [v.name for v in tf.trainable_variables()]
            variable_shapes = [v.get_shape() for v in tf.trainable_variables()]
            for name, shape in zip(variable_names, variable_shapes):
                print('{}\nShape: {}'.format(name, shape))

            num_batches = ceil(trainset.size()[0] / batch_size)
            for epoch in range(1, epochs + 1):
                for batch in range(1, num_batches + 1):
                    batch_x, batch_y, batch_seqlen = trainset.next(batch_size)
                    # Run optimization op (backprop)
                    sess.run(optimizer, feed_dict={self.x: batch_x, self.y: batch_y, self.seqlen: batch_seqlen})
                if epoch % 8 is 0 or epoch is 1:
                    print('epoch # %d' % epoch, 'accuracy: %f' % self.calc_accuracy(testset, sess, batch_size))

            print("Optimization Finished!")

    def calc_accuracy(self, dataset, sess, batch_size):

        ''' Calculate accuracy on dataset '''

        # Evaluate model
        correct_pred = tf.equal(tf.argmax(self.bi_lstm, 1), tf.argmax(self.y, 1))
        accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

        n_test_batches = ceil(dataset.size()[0] / batch_size)
        global_matches = 0

        batch_matches = tf.reduce_sum(tf.cast(correct_pred, tf.float32))
        for batch in range(1, n_test_batches + 1):
            batch_x, batch_y, batch_seqlen = dataset.next(batch_size)
            global_matches += sess.run(batch_matches, feed_dict={self.x: batch_x,
            self.y: batch_y, self.seqlen: batch_seqlen})

        return global_matches / float(dataset.size()[0])

