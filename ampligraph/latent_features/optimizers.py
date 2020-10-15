import tensorflow as tf
import abc
import logging
import six

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OptimizerWrapper(abc.ABC):
    """Wrapper around tensorflow optimizer
    """
    def __init__(self, optimizer=None):
        """Initialize the Optimizer
        
        Parameters:
        -----------
        optimizer: String (name of optimizer) or optimizer instance. 
            See `tf.keras.optimizers`.
        """ 
        self.optimizer = optimizer
        self.num_optimized_vars = 0
        self.number_hyperparams = -1
        
        # workaround for Adagrad/Adadelta/Ftrl optimizers to work on gpu
        self.gpu_workaround = False
        if isinstance(self.optimizer, tf.keras.optimizers.Adadelta) or \
            isinstance(self.optimizer, tf.keras.optimizers.Adagrad) or \
                isinstance(self.optimizer, tf.keras.optimizers.Ftrl):
            self.gpu_workaround = True

    def apply_gradients(self, grads_and_vars):
        """Wrapper around apply_gradients. 
        See https://www.tensorflow.org/api_docs/python/tf/keras/optimizers for more details.
        """
        self.optimizer.apply_gradients(grads_and_vars)
        
    def minimize(self, loss, ent_emb, rel_emb, gradient_tape, other_vars=[]):
        '''Minimizes the loss with respect to entity, relation embeddings and other trainable vars
        
        Parameters:
        -----------
        loss: tf.Tensor
            Model Loss
        ent_emb: tf.Variable
            entity embedding 
        rel_emb: tf.Variable
            relation embedding
        gradient tape: tf.GradientTape
            gradient tape under which the loss computation was tracked
        other_vars: list
            list of all other trainable variables
        '''
        all_trainable_vars = [ent_emb, rel_emb]
        all_trainable_vars.extend(other_vars)
        # Total number of trainable variables in the graph
        self.num_optimized_vars = len(all_trainable_vars)
        
        if self.gpu_workaround:
            # workaround - see the issue:
            # https://github.com/tensorflow/tensorflow/issues/28090 
            with gradient_tape:
                loss += (0.0000 * (tf.reduce_sum(ent_emb) + tf.reduce_sum(rel_emb)))
            
        # Compute gradient of loss wrt trainable vars
        gradients = gradient_tape.gradient(loss, all_trainable_vars)
        # update the trainable params
        self.optimizer.apply_gradients(zip(gradients, all_trainable_vars))
        
        # Compute the number of hyperparameters related to the optimizer
        # if self.__number_hyperparams == -1:
        #    optim_weights = self._optimizer.get_weights()
        #    self.__number_hyperparams = 0
        #    for i in range(1, len(optim_weights), self.__num_optimized_vars):
        #        self.__number_hyperparams += 1

    def get_hyperparam_count(self):
        ''' Number of hyperparams of the optimizer being used
        Eg: adam has beta1 and beta2. if we use amsgrad argument then it has 3
        '''
        return self.number_hyperparams
    
    def get_entity_relation_hyperparams(self):
        ''' Get optimizer hyperparams related to entity and relation embeddings (for partitioned training)
        
        Returns:
        --------
        ent_hyperparams: np.array
            entity embedding related optimizer hyperparameters
        rel_hyperparams: np.array
            relation embedding related optimizer hyperparameters
        '''    
        optim_weights = self.optimizer.get_weights()
        ent_hyperparams = []
        rel_hyperparams = []
        for i in range(1, len(optim_weights), self.num_optimized_vars):
            ent_hyperparams.append(optim_weights[i])
            rel_hyperparams.append(optim_weights[i + 1])
            
        return ent_hyperparams, rel_hyperparams
    
    def set_entity_relation_hyperparams(self, ent_hyperparams, rel_hyperparams):
        ''' Sets optimizer hyperparams related to entity and relation embeddings (for partitioned training)
        
        Parameters:
        -----------
        ent_hyperparams: np.array
            entity embedding related optimizer hyperparameters
        rel_hyperparams: np.array
            relation embedding related optimizer hyperparameters
        '''
        optim_weights = self.optimizer.get_weights()
        for i, j in zip(range(1, len(optim_weights), self.num_optimized_vars), range(len(ent_hyperparams))):
            optim_weights[i] = ent_hyperparams[j]
            optim_weights[i + 1] = rel_hyperparams[j]
        self.optimizer.set_weights(optim_weights)
        
    def get_weights(self):
        """Wrapper around get weights.
        See https://www.tensorflow.org/api_docs/python/tf/keras/optimizers for more details.
        """
        return self.optimizer.get_weights()
        
    def set_weights(self, weights):
        """Wrapper around set weights.
        See https://www.tensorflow.org/api_docs/python/tf/keras/optimizers for more details.
        """
        self.optimizer.set_weights(weights)

    def get_iterations(self):
        return self.optimizer.iterations.numpy()
        

def get(identifier):
    if isinstance(identifier, tf.optimizers.Optimizer):
        return OptimizerWrapper(identifier)
    elif isinstance(identifier, OptimizerWrapper):
        return identifier
    elif isinstance(identifier, six.string_types):
        optimizer = tf.keras.optimizers.get(identifier)
        return OptimizerWrapper(optimizer)
    else:
        raise ValueError('Could not interpret optimizer identifier:', identifier)
