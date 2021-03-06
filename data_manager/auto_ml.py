# Imports
import numpy as np
import os
from sklearn.model_selection import train_test_split
import pandas as pd
from utilities import *
import matplotlib.pyplot as plt
import seaborn as sns

class AutoML():
    def __init__(self, input_dir="", basename="", test_size=0.2, verbose=False):
        """
            Constructor.
            Recover all autoML files available and build the AutoML structure containing them.
            :param input_dir: The directory where the autoML files are stored.
            :param basename: The name of the dataset (i.e. the prefix in the name of the files) 
                                Example : files = ('iris.data', iris_feat.name', etc.)
                                          basename = 'iris'
            :param test_size: Proportion of the dataset to include in the test split.
            :param verbose: Display additional information during run.
        """
        if os.path.isdir(input_dir):
            self.input_dir = input_dir
        else:
            raise OSError(
                'Input directory {} does not exist.'.format(input_dir))

        self.basename = basename
        if os.path.exists(os.path.join(self.input_dir, basename + '_train.data')) or \
         os.path.exists(os.path.join(self.input_dir, basename + '.data')):
            self.basename = basename
        else:
            raise OSError('No .data files found')

        # Data
        self.data = dict()
        self.init_data(test_size=test_size)
        
        # Processed data
        self.processed_data = None # None while no processing has been done

        # autoML info
        self.info = dict()
        self.init_info(
            os.path.join(self.input_dir, self.basename + '_public.info'), verbose=verbose)

        self.feat_name = self.load_name(
            os.path.join(self.input_dir, self.basename + '_feat.name'))
        self.label_name = self.load_name(
            os.path.join(self.input_dir, self.basename + '_label.name'))
            
        # Type of each variable
        self.feat_type = self.load_type(
            os.path.join(self.input_dir, self.basename + '_feat.type'))
        self.is_numerical = self.compute_feat_type() # to prevent error with functions that needs it

        # Meta-features
        self.descriptors = dict()
        self.compute_descriptors()

    @classmethod
    def from_df(cls, input_dir, basename, X, y=None):
        """
            Class Method
            Build AutoML structure from Pandas DataFrame.
            Generates autoML files from Pandas DataFrame, write them on disk and call the AutoML constructor.
            
            :param input_dir: The directory where the autoML files will be stored.
            :param basename: The name of the dataset.
            :param X: Dataset containing the samples.
            :param y: Dataset containing the labels (optional if no labels).
        """
        def write(filepath, X):
            np.savetxt(filepath, X, fmt='%s')

        if not os.path.isdir(input_dir):
            os.mkdir(input_dir)

        path = input_dir + '/' + basename
        write(path + ".data", X.values)
        write(path + "_feat.name", X.columns.values)
        write(path + "_feat.type", X.dtypes)

        if y is not None:
            write(path + ".solution", y.values)
            write(path + "_label.name", [y.name])

        return cls(input_dir, basename)

    @classmethod
    def from_csv(cls, input_dir, basename, X_path, y_path=None, X_header='infer', y_header='infer'):
        """
            Class Method
            Build AutoML structure from CSV file.
            Generates autoML files from CSV file, write them on disk and call the AutoML constructor.
            
            :param input_dir: The directory where the autoML files will be stored.
            :param basename: The name of the dataset.
            :param X_path: path of the .csv containing the samples.
            :param y_path: path of the .csv containing the labels (optional if no labels).
            :param X_header: header (parameter under review)
            :param Y_header: header (parameter under review)
        """
        if os.path.exists(os.path.join(input_dir, X_path)):
            X = pd.read_csv(os.path.join(input_dir, X_path), header=X_header)
        else:
            raise OSError('{} file does not exist'.format(X_path))

        if y_path and os.path.exists(os.path.join(input_dir, y_path)):
            y = pd.read_csv(os.path.join(input_dir, y_path), header=y_header)
        else:
            y = None
            #y = X.iloc[:, -1]
            #X = X.iloc[:, :-1]

        return cls.from_df(input_dir, basename, X, y)

    def init_data(self, test_size=0.2):
        """
            Load .data autoML files in a dictionary.
            
            :param test_size: If data is not splitted in autoML files, size of the test set.
                                Example : files = (i.e 'iris.data')
                                          test_size = 0.5
                                -> Data will be splitted 50% in X_train and 50% in X_test
            .. note:: If data is not splitted (i.e. no '_train.data', '_test.data'), samples are loaded in X_train.
        """
        if os.path.exists(
                os.path.join(self.input_dir, self.basename + '_train.data')):
            self.data['X_train'] = self.load_data(
                os.path.join(self.input_dir, self.basename + '_train.data'))
            self.data['X_test'] = self.load_data(
                os.path.join(self.input_dir, self.basename + '_test.data'))
            self.data['X'] = self.data['X_train'] + self.data['X_test']
            if os.path.exists(
                os.path.join(self.input_dir, self.basename + '_train.solution')):
                self.data['y_train'] = self.load_label(
                    os.path.join(self.input_dir, self.basename + '_train.solution'))
                self.data['y_test'] = self.load_label(
                    os.path.join(self.input_dir, self.basename + '_test.solution'))
                self.data['y'] = self.data['y_train'] + self.data['y_test']
        elif os.path.exists(
                os.path.join(self.input_dir, self.basename + '.data')):
            self.data['X'] = self.load_data(
                os.path.join(self.input_dir, self.basename + '.data'))  
            if os.path.exists(os.path.join(self.input_dir, self.basename + '.solution')):
                self.data['y'] = self.load_label(
                    os.path.join(self.input_dir, self.basename + '.solution'))
            self.train_test_split(test_size=test_size)
            
        else:
            raise OSError('No .data files in {}.'.format(self.input_dir))

    def train_test_split(self, **kwargs):
        """ Apply the train test split
        """
        if 'y' in self.data:
            self.data['X_train'], self.data['X_test'], self.data['y_train'], self.data['y_test'] = \
                 train_test_split(self.data['X'], self.data['y'], **kwargs)
        else:
        
            cut = int(np.floor(self.data['X'].shape[0] * 0.8))
            if 'test_size' in kwargs:
                cut = int(np.floor(self.data['X'].shape[0] * (1 - kwargs.get('test_size'))))
            elif 'train_size' in kwargs:
                cut = int(np.floot(self.data['X'].shape[0] * kwargs.get('train_size')))
            
            shuffle = True
            if 'shuffle' in kwargs:
                shuffle = kwargs.get('shuffle')
                
            if shuffle:
                self.data['X_train'], self.data['X_test'] = np.random.permutation(self.data['X'])[:cut], \
                                                                        np.random.permutation(self.data['X'][cut:])
            else:
                self.data['X_train'], self.data['X_test'] = self.data['X'][:cut], self.data['X'][cut:]
                
        return self.data


    def load_data(self, filepath):
        """
            Load a .data autoML file in an array.
            :param filepath: path of the file.
            :return: array containing the data. 
            :rtype: numpy array
        """
        return pd.read_csv(filepath, sep=' ', header=None).values if os.path.exists(filepath) \
          else []

    def load_label(self, filepath):
        """ 
            Load a .solution autoML file in an array.
            :param filepath: Path of the file.
            :return: Array containing the data labels. 
            :rtype: Numpy Array
        """
        return pd.read_csv(filepath, sep=' ', header=None).values if os.path.exists(filepath) \
          else []

    def load_name(self, filepath):
        """
            Load a _feat.name autoML file in an array.
            If None, return an array of variables [X1, ..., XN] (with N the number of features).
                   
            :param filepath: Path of the file.
            :return: Array containing the data names. 
            :rtype: Numpy Array
        """
        return pd.read_csv(filepath, header=None).values.ravel() if os.path.exists(filepath) \
          else ['X' + str(i) for i in range(self.info['feat_num'])]

    def load_type(self, filepath):
        """
            Load a _feat.type autoML file in an array.
            If None, compute it.
                   
            :param filepath: Path of the file.
            :return: Array containing the data types. 
            :rtype: Numpy Array
        """
        return pd.read_csv(filepath, header=None).values.ravel() if os.path.exists(filepath) \
          else self.compute_feat_type()

    def init_info(self, filepath, verbose=True):
        """
            Load a _public.info autoML file in a dictionary.
            If None, build the dictionary on its own.
                   
            :param filepath: Path of the file.
            :return: Dictionary containing the data information. 
            :rtype: Dict
        """
        if os.path.exists(filepath):
            df = pd.read_csv(
                os.path.join(self.input_dir, self.basename + '_public.info'),
                header=None,
                sep='=').values
            for x in df:
                x[0] = x[0].replace("'", '').strip()
                x[1] = x[1].replace("'", '').strip()
                # Convert numerical information in int instead of str
                for v in x[1]:
                    try:
                        x[1] = int(x[1])
                    except:
                        pass
            self.info = dict(zip(df[:, 0], df[:, 1]))

        else:
            if verbose:
                print('No info file found.')

            if os.path.exists(
                    os.path.join(self.input_dir, self.basename + '.data')):
                self.get_type_problem(
                    os.path.join(self.input_dir, self.basename + '.solution'))
            else:
                self.get_type_problem(
                    os.path.join(self.input_dir, self.basename + '_train.solution'))

            self.info['format'] = 'dense'
            self.info['is_sparse'] = 0
            self.info['train_num'], self.info['feat_num'] = self.data['X_train'].shape
            if ('y_train' in self.data) and ('y_test' in self.data) and ('X_train' in self.data):
                self.info['target_num'] = self.data['y_train'].shape[1]
                self.info['test_num'] = self.data['X_test'].shape[0]
                assert (self.info['train_num'] == self.data['y_train'].shape[0])
                assert (self.info['feat_num'] == self.data['X_test'].shape[1])
                assert (self.info['test_num'] == self.data['y_test'].shape[0])
                assert (self.info['target_num'] == self.data['y_test'].shape[1])
            self.info['usage'] = 'No info file'
            self.info['name'] = self.basename
            self.info['has_categorical'] = 0
            self.info['has_missing'] = 0
            self.info['feat_type'] = 'mixed'
            self.info['time_budget'] = 600
            self.info['metric'] = 'r2_metric' if self.info['task'] == 'regression' else 'auc_metric'

        return self.info

    def get_data_as_df(self):
        """ 
            Get data as a dictionary of pandas DataFrame.
            
            :return: Dictionary containing the data as pandas DataFrame.
            :rtype: Dict
        """
        data = dict()
        
        # X/y
        data['X'] = pd.DataFrame(self.data['X'], columns=self.feat_name)
        if 'y' in self.data:
            data['y'] = pd.DataFrame(self.data['y'], columns=self.label_name)

        # Train/test
        if 'X_train' and 'X_test' in self.data:
            data['X_train'] = pd.DataFrame(
                self.data['X_train'], columns=self.feat_name)
            data['X_test'] = pd.DataFrame(
                self.data['X_test'], columns=self.feat_name)
            if 'y_train' and 'y_test' in self.data:
                data['y_train'] = pd.DataFrame(
                    self.data['y_train'], columns=self.label_name)
                data['y_test'] = pd.DataFrame(
                    self.data['y_test'], columns=self.label_name)
                    
        return data

    def save(self, out_path, out_name):
        """ Save data in auto_ml file format
        
            :param out_path: Path of output directory.
            :param out_name: Basename of output files.
        """
        def write_array(path, X):
            np.savetxt(path, X, fmt='%s')

        if not os.path.isdir(out_path):
            os.makedirs(out_path)

        write_array(
            os.path.join(out_path, out_name + '.data'),
            self.data['X'])
        write_array(
            os.path.join(out_path, out_name + '_feat.name'), 
            self.feat_name)

        if 'y' in self.data:
            write_array(
                os.path.join(out_path, out_name + '.solution'),
                self.data['y'])

        if 'X_train' and 'X_test' in self.data:
            write_array(
                os.path.join(out_path, out_name + '_train.data'),
                self.data['X_train'])
            write_array(
                os.path.join(out_path, out_name + '_test.data'),
                self.data['X_test'])
            if 'y_train' and 'y_test' in self.data:
                write_array(
                    os.path.join(out_path, out_name + '_test.solution'),
                    self.data['y_train'])
                write_array(
                    os.path.join(out_path, out_name + '_test.solution'),
                    self.data['y_test'])
                write_array(
                    os.path.join(out_path, out_name + '_label.name'),
                    self.label_name)

        with open(os.path.join(out_path, out_name + '_public.info'), 'w') as f:
            for key, item in self.info.items():
                f.write(str(key))
                f.write(' = ')
                f.write(str(item))
                f.write('\n')

    def get_type_problem(self, solution_filepath):
        """ 
            Get the type of problem directly from the solution file (in case we do not have an info file).
            :param solution_filepath: Path of the file
            :return: Type of the problem stored in the info dict attribute as 'task'
            :rtype: str
        """
        if 'task' not in self.info.keys() and 'y_train' in self.data:
            solution = pd.read_csv(
                solution_filepath, sep=' ', header=None).values
            target_num = solution.shape[1]
            self.info['target_num'] = target_num
            if target_num == 1:  # if we have only one column
                solution = np.ravel(solution)  # flatten
                nbr_unique_values = len(np.unique(solution))
                if nbr_unique_values < len(solution) / 8:
                    # Classification
                    self.info['label_num'] = nbr_unique_values
                    if nbr_unique_values == 2:
                        self.info['task'] = 'binary.classification'
                        self.info['target_type'] = 'binary'
                    else:
                        self.info['task'] = 'multiclass.classification'
                        self.info['target_type'] = 'categorical'
                else:
                    # Regression
                    self.info['label_num'] = 0
                    self.info['task'] = 'regression'
                    self.info['target_type'] = 'numerical'
            else:
                # Multilabel or multiclass
                self.info['label_num'] = target_num
                self.info['target_type'] = 'binary'
                if any(item > 1 for item in map(np.sum, solution.astype(int))):
                    self.info['task'] = 'multilabel.classification'
                else:
                    self.info['task'] = 'multiclass.classification'
        else:
            self.info['task'] = 'Unknown'
        return self.info['task']

    def get_processed_data(self, encoding='label', normalization='mean'):
        """ 
            Preprocess data.
            - Missing values inputation
            - +Inf and -Inf replaced by maximum and minimum
            - Encoding ('label', 'one-hot') for categorical variables
            - Normalization ('mean', 'min-max', None)
            :param encoding: 'label', 'one-hot'
            :param normalization: 'mean', 'min-max' 
            :return: Dictionnary containing the preprocessed data as Pandas DataFrame
            :rtype: Dict
        """
        if self.processed_data == None:
            self.processed_data = dict()
            data_df = self.get_data_as_df()

            for k in list(data_df.keys()):
                self.processed_data[k] = preprocessing(data_df[k], encoding=encoding, normalization=normalization)

        return self.processed_data

    def compute_feat_type(self):
        """ For each variable, compute if it is numerical, categorical, etc.
        
            :return: List of strings, each string represent the type of a variable.
            :rtype: list
        """
        feat_type = []
        
        data = self.get_data_as_df()['X']
        columns = data.columns.values
        for column in columns:
            # For numerical variables
            if is_numeric(data[column]):
                feat_type.append('numerical')
            else:
                feat_type.append('mixed')
                
        return feat_type

    def compute_descriptors(self):
        """ 
            Compute descriptors of the dataset and store them in the descriptors dictionary.
            - ratio: Dataset ratio
            - symb_ratio: Ratio of symbolic attributes
            - class_deviation: Standard deviation of class distribution
            - missing_proba: Probability of missing values
            - skewness_min: Minimum skewness over features 
            - skewness_max: Maximum skewness over features
            - skewness_mean: Average skewness over features
        """ # - defective_proba: Probability of defective records (columns with missing values)
        data_as_df = self.get_data_as_df()
        
        self.descriptors['ratio'] = int(self.info['feat_num']) / int(self.info['train_num'])
            
        self.descriptors['symb_ratio'] = self.is_numerical.count('numeric') / len(self.is_numerical)
        
        if 'y' in self.data:
             self.descriptors['class_deviation'] = data_as_df['y'].std().mean()
        
        self.descriptors['missing_proba'] = (data_as_df['X'].isnull().sum() / len(data_as_df['X'])).mean()
            
        skewness = data_as_df['X'].skew()
        self.descriptors['skewness_min'] = skewness.min()
        self.descriptors['skewness_max'] = skewness.max()
        self.descriptors['skewness_mean'] = skewness.mean()
        

    def show_info(self):
        """ Show AutoML info 
        """
        for k in list(self.info.keys()):
            key = k.capitalize().replace('_', ' ')
            value = self.info[k]
            if isinstance(value, str):
                value = value.capitalize().replace('_', ' ').replace('.', ' ')

            print('{}: {}'.format(key, value))
          
    #def show_feat_type(self):
    #    """ Display type of each variable (numerical, categorical, etc.)
    #    """
    #    display(self.feat_type)
    #    is_numerical

    def show_descriptors(self, processed_data=False):
        """ 
            Show descriptors of the dataset.
            
            Descriptors:
            - ratio: Dataset ratio
            - symb_ratio: Ratio of symbolic attributes
            - class_deviation: Standard deviation of class distribution
            - missing_proba: Probability of missing values
            - skewness_min: Minimum skewness over features 
            - skewness_max: Maximum skewness over features
            - skewness_mean: Average skewness over features
            
            Plots:
            - Scatter plot features matrix
            - Classes distribution
            - Correlation matrix
            - Hierarchical clustering heatmap
            - First two principal components
            - First two LDA components
            - T-SNE plot
            
            :param processed_data: Boolean defining whether to display the
                                    descriptors of the raw data or the processed data
        """
        
        if processed_data:
            data = self.get_processed_data()
        else:
            data = self.get_data_as_df()

        # Text
        printmd('** Descriptors **')

        for k in list(self.descriptors.keys()):
            key = k.capitalize().replace('_', ' ')
            value = self.descriptors[k]
            if isinstance(value, str):
                value = value.capitalize().replace('_', ' ').replace('.', ' ')

            print('{}: {}'.format(key, value))

        # Plots
        print('')
        printmd('** Plots **')
        
        x_sets = ['X_train']
        y_sets = []
        
        # If there is a class
        if 'y_train' in self.data:
            y_sets.append('y_train')
            y_sets.append('y_test')
        
        # If there is a test set
        if (len(self.data['X_test']) > 0):
            x_sets.append('X_test')

        if int(self.info['feat_num']) < 20: # TODO selection, plot with y
            printmd('** Scatter plot matrix **')
            sns.set(style="ticks")
            for x in x_sets:
                print(x)
                sns.pairplot(data[x]) 
                plt.show()

        printmd('** Correlation matrix **')
        for x in x_sets:
            print(x)
            show_correlation(data[x])

        printmd('** Hierarchical clustering heatmap **')
        for x in x_sets:
            print(x)
            # row_method, column_method, row_metric, column_metric, color_gradient
            heatmap(data[x], 'average', 'single', 'euclidean',
                    'euclidean', 'coolwarm')

        if len(y_sets) > 0:
        
            printmd('** Classes distribution **')
            for y in y_sets:
                print(y)
                show_classes(data[y])
        
            printmd('** Principal components analysis **')
            for i in range(len(x_sets)):
                print(x_sets[i])
                print(y_sets[i])
                show_pca(data[x_sets[i]], data[y_sets[i]])

            printmd('** T-distributed stochastic neighbor embedding **')
            for i in range(len(x_sets)):
                print(x_sets[i])
                print(y_sets[i])
                show_tsne(data[x_sets[i]], data[y_sets[i]])

            printmd('** Linear discriminant analysis **')
            for i in range(len(x_sets)):
                print(x_sets[i])
                print(y_sets[i])
                show_lda(data[x_sets[i]], data[y_sets[i]])