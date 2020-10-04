import pydicom
import json
import six

# TODO: what is pydicom practice for logging?
def logger_debug(message):
   print(message)
def logger_warning(message):
   print(message)

# TODO: is this the whole list?
_BINARY_VR_VALUES = ['OW', 'OB', 'OD', 'OF', 'OL', 'UN', 'OW/OB', 'OW or OB', 'OB or OW', 'US or SS']

# TODO: these don't get auto-quoted by json for some reason
_VRs_TO_QUOTE = ['DS', 'AT']

def _create_dataelement(tag, vr, value):
    '''Creates a DICOM Data Element.
    Parameters
    ----------
    tag: pydicom.tag.Tag
        data element tag
    vr: str
        data element value representation
    value: list
        data element value(s)
    Returns
    -------
    pydicom.dataelem.DataElement
    '''
    try:
        vm = dicom.datadict.dictionaryVM(tag)
    except KeyError:
        # Private tag
        vm = str(len(value))
    if vr not in _BINARY_VR_VALUES:
        if not(isinstance(value, list)):
            raise DICOMJSONError(
                '"Value" of data element "{}" must be an array.'.format(tag)
            )
    if vr == 'SQ':
        elem_value = []
        for value_item in value:
            ds = _init_dataset()
            if value_item is not None:
                for key, val in value_item.items():
                    if 'vr' not in val:
                        raise DICOMJSONError(
                            'Data element "{}" must have key "vr".'.format(tag)
                        )
                    supported_keys = {'Value', 'BulkDataURI', 'InlineBinary'}
                    val_key = None
                    for k in supported_keys:
                        if k in val:
                            val_key = k
                            break
                    if val_key is None:
                        logger_debug(
                            'data element has neither key "{}".'.format(
                                '" nor "'.join(supported_keys)
                            )
                        )
                        e = dicom.dataelem.DataElement(
                            tag=tag, value=None, VR=vr
                        )
                    else:
                        e = _create_dataelement(key, val['vr'], val[val_key])
                    ds.add(e)
            elem_value.append(ds)
    elif vr == 'PN':
        # Special case, see DICOM Part 18 Annex F2.2
        elem_value = []
        for v in value:
            if not isinstance(v, dict):
                # Some DICOMweb services get this wrong, so we workaround the
                # the issue and warn the user rather than raising an error.
                logger_warning(
                    'attribute with VR Person Name (PN) is not '
                    'formatted correctly'
                )
                elem_value.append(v)
            else:
                elem_value.extend(list(v.values()))
        if vm == '1':
            try:
                elem_value = elem_value[0]
            except IndexError:
                elem_value = None
    else:
        if vm == '1':
            if vr in _BINARY_VR_VALUES:
                elem_value = value
            else:
                if value:
                    elem_value = value[0]
                else:
                    elem_value = value
        else:
            if len(value) == 1 and isinstance(value[0], six.string_types):
                elem_value = value[0].split('\\')
            else:
                elem_value = value
    if value is None:
        logger_warning('missing value for data element "{}"'.format(tag))
    try:
        return dicom.dataelem.DataElement(tag=tag, value=elem_value, VR=vr)
    except Exception:
        raise ValueError(
            'Data element "{}" could not be loaded from JSON: {}'.format(
                tag, elem_value
            )
        )



def _data_element_to_json(data_element, element_handler):
    """Returns a json dictionary which is either a single
    element or a dictionary of elements representing a sequnce.
    """
    json_element = None
    if data_element.VR in _BINARY_VR_VALUES:
        if element_handler:
            # TODO: provide some example element_handler implementations
            value = element_handler(data_element)
        else:
            value = "Binary Omitted" # TODO
    elif data_element.VR == "SQ":
        values = []
        for subelement in data_element:
            # recursive call to co-routine to format sequence contents
            values.append(to_json(subelement))
        value = values
    elif data_element.VR in _VRs_TO_QUOTE:
        # TODO: switch to " from ' - why doesn't json do this?
        value = ["%s" % data_element.value]
    elif data_element.VR == "PN":
        value = data_element.value
        if value is not None:
            value = [{ "Alphabetic" : value.original_string }]
    else:
        value = data_element.value
        if value is not None:
            value = [value]
    try:
        json_element = {
            "vr" : data_element.VR,
        }
        if value is not None:
            json_element["Value"] = value
    except UnboundLocalError as e:
        # TODO: there should be a better way to catch this
        print(e)
        print ("UnboundLocalError: ", data_element)
    return json_element

def from_json(json_dataset):
    '''Loads DICOM Data Set in DICOM JSON format.
    Parameters
    ----------
    json_dataset: json string that uses the DICOM JSON Model (Annex F format)

    Returns
    -------
    dicom.dataset.Dataset
    '''

    dataset = dicom.dataset.Dataset()

    json_dataset_object = json.loads(json_dataset)
    for tag, mapping in json_dataset_object.items():
        vr = mapping['vr']
        try:
            value = mapping['Value']
        except KeyError:
            logger_debug(
                'mapping for data element "{}" has no "Value" key'.format(tag)
            )
            value = [None]
        group,element = "0x"+tag[0:4], "0x"+tag[5:9]
        data_element = _create_dataelement((group, element), vr, value)
        dataset.add(data_element)
    return dataset

def to_json(dataset, element_handler=None):
    """
    Parameters
    ----------
    dataset: dicom.dataset.Dataset

    Returns
    -------
    A json string of the DICOM JSON Model of the datset
    will convert into json of the form documented here:
    ftp://medical.nema.org/medical/dicom/final/sup166_ft5.pdf
    Note this is a co-routine with _data_element_to_json and they
    can call each other recursively since SQ (sequence) data elements
    are implemented as nested datasets.
    """
    json_dataset_object = {}
    for key in dataset.keys():
        jkey = "%04X%04X" % (key.group,key.element)
        try:
            dataElement = dataset[key]
            json_dataset_object[jkey] = _data_element_to_json(dataElement, element_handler)
        except KeyError:
            print("KeyError: ", key)
        except ValueError:
            print("ValueError: ", key)
        except NotImplementedError:
            print("NotImplementedError: ", key)
    json_dataset = json.dumps(json_dataset_object)
    return json_dataset


"""

execfile('/Users/pieper/slicer4/latest/SlicerWeb/WebServer/json.py'); dicom_json_test()

"""


def dicom_json_test():

    json_dataset = """{
        "00080005": { "vr": "CS", "Value": [ "ISO_IR 100" ] },
        "00080020": { "vr": "DA", "Value": [ "20180227" ] },
        "00080030": { "vr": "TM", "Value": [ "091932" ] },
        "00080050": { "vr": "SH", "Value": [ "2015031299" ] },
        "00080054": { "vr": "AE", "Value": [ "DCM4CHEE" ] },
        "00080056": { "vr": "CS", "Value": [ "ONLINE" ] },
        "00080061": { "vr": "CS", "Value": [ "SM" ] },
        "00080090": { "vr": "PN" }, "00081190": { "vr": "UR", "Value": [
            "http://server.dcmjs.org/dcm4chee-arc/aets/DCM4CHEE/rs/studies/1.2.392.200140.2.1.1.1.2.799008771.2448.1519719572.518"
          ]
        },
        "00100010": { "vr": "PN" },
        "00100020": { "vr": "LO", "Value": [ "PID_08154711" ] },
        "00100030": { "vr": "DA" },
        "00100040": { "vr": "CS" },
        "0020000D": { "vr": "UI", "Value": [ "1.2.392.200140.2.1.1.1.2.799008771.2448.1519719572.518" ] },
        "00200010": { "vr": "SH", "Value": [ "SID_1001" ] },
        "00201206": { "vr": "IS", "Value": [ 1 ] },
        "00201208": { "vr": "IS", "Value": [ 6 ] }
      }"""

    dataset = from_json(json_dataset)
    roundtrip_json_dataset = to_json(dataset)

    print(json_dataset)
    print(dataset)
    print(json.dumps(json.loads(roundtrip_json_dataset), indent=4, sort_keys=True))
