#include <sendas.h>

#include <mtclreg.h>                        // for CClientMtmRegistry 
#include <msvstd.h>                         // for TMsvId
#include <mmsclient.h>                      // for CMmsClientMtm
#include <mtmdef.h>                         // for KMsvMessagePartDescription etc.
#include <mtclbase.h>                       // for CBaseMtm

#include <Python.h>
#include "symbian_python_ext_util.h"
	
class TSendAsObserver : public MSendAsObserver
{
public:
    virtual TBool CapabilityOK(TUid aCapabilty, TInt aResponse)
    {
        return ETrue;
    }
};

/*
mms_send

Sends a multimedia (MMS) message. Arguments are

1. Recipient address. Phone number or email address. Unicode string.
2. Text contents of the message. Unicode string.
3. File name of an attachment (eg. an image file). Unicode string. 

Returns: error code, from the TRequestStatus of the asynchronous operation, 0 if ok

Exceptions: PyExc_SystemError

Called from Python as

    import mmsmodule
    retcode = mmsmodule.mms_send(u"012345678", u"Test message", u"e:\\temp\\image.jpg")

Author: Kari Kujansuu (kari.kujansuu@operamail.com)

*/
static PyObject *
mms_sendL(TPtrC address_desc, TPtrC msg_desc, TPtrC filename_desc); 

static PyObject *
mms_sendtomanyL(PyObject* addrs, TPtrC msg_desc, PyObject* files);

static PyObject * 
mms_send(PyObject *self, PyObject *args)
{
    char *address;
    char *msg;
    char *filename;

    int addrlen;
    int msglen;
    int fnamelen;

    if (!PyArg_ParseTuple(args, "u#u#u#"
            , &address,  &addrlen
            , &msg,      &msglen
            , &filename, &fnamelen
        ))
        return NULL;

    TPtrC address_desc((TUint16*)address, addrlen);
    TPtrC msg_desc((TUint16*)msg, msglen);
    TPtrC filename_desc((TUint16*)filename, fnamelen);
    PyObject* ret;
    TRAPD( error, ret = mms_sendL(address_desc, msg_desc, filename_desc ) );
    if (error != KErrNone)
        RETURN_ERROR_OR_PYNONE(error);
    return ret;
}

static PyObject * 
mms_sendtomany(PyObject *self, PyObject *args)
{
    char *msg;
    int msglen;
    PyObject* addresses;
    PyObject* filenames;
    if (!PyArg_ParseTuple(args, "Ou#O"
            , &addresses, &msg, &msglen, &filenames))
        return NULL;
    TPtrC msg_desc((TUint16*)msg, msglen);
    PyObject* addrs;
    PyObject* files;
    addrs = PySequence_Fast(addresses, "expected a sequence for addresses");
    files = PySequence_Fast(filenames, "expected a sequence for filenames");

    PyObject* ret = NULL;
    TRAPD( error, ret = mms_sendtomanyL(addrs, msg_desc, files) );

    Py_DECREF(addrs);
    Py_DECREF(files);

    if (error != KErrNone)
        RETURN_ERROR_OR_PYNONE(error);
    return ret;
}

static PyObject *
mms_sendL(TPtrC address_desc, TPtrC msg_desc, TPtrC filename_desc)
{
	TSendAsObserver observer;

    CSendAs* sendas = CSendAs::NewL(observer);
    CleanupStack::PushL(sendas);

    sendas->SetMtmL(KUidMsgTypeMultimedia); // MMS type -  KUidMsgTypeMMS?
    sendas->SetService(0); // first and only MMS service? is this needed at all?
    sendas->CreateMessageL();

    sendas->AddRecipientL(address_desc);
    sendas->SetSubjectL(msg_desc);

    TMsvId attachmentId;

    CMmsClientMtm& mtm = (CMmsClientMtm&)sendas->ClientMtm();
    mtm.CreateAttachment2L( attachmentId, filename_desc );

    TMsvPartList partlist = sendas->ValidateMessage();
    if (partlist != 0)
    {   
        // msg invalid
        // set exception 
        PyErr_SetString(PyExc_SystemError, "ValidateMessage failed"); 
        CleanupStack::PopAndDestroy(sendas); 
        return NULL;
    }

    sendas->SaveMessageL(ETrue);


// the following copied from Nokia example MMSDemo1Engine.cpp (MMSDemo1_v1_0.zip,
// Series 60 Developer Platform: MMSDemo1 Example v1.0, 03-Apr-2003):

    // Start sending the message via the Server MTM to the MMS server
    CMsvOperationWait* wait = CMsvOperationWait::NewLC(); // left in CS
    wait->iStatus = KRequestPending; 

    CMsvOperation* op = NULL;
    op = mtm.SendL( wait->iStatus );
    CleanupStack::PushL( op );
    wait->Start();

    // Added Py_BEGIN_ALLOW_THREADS/Py_END_ALLOW_THREADS according to advice from Jukka Laurila:
    // You should release the interpreter lock before entering the Active Scheduler and reacquire it 
    // when you return from it. Whenever you call CActiveScheduler::Start() in a Python extension you should do this.
    Py_BEGIN_ALLOW_THREADS
    CActiveScheduler::Start();
    Py_END_ALLOW_THREADS      

    // The following is to ignore the completion of other active objects. It is not
    // needed if the app has a command absorbing control.
    while( wait->iStatus.Int() == KRequestPending )
    {
        Py_BEGIN_ALLOW_THREADS
        CActiveScheduler::Start();
        Py_END_ALLOW_THREADS      
    }

    CleanupStack::PopAndDestroy(2); // op, wait
    CleanupStack::PopAndDestroy(sendas); 

    return Py_BuildValue("i", wait->iStatus.Int());
}

static PyObject *
mms_sendtomanyL(PyObject* addrs, TPtrC msg_desc, PyObject* files)
{
	TSendAsObserver observer;

    CSendAs* sendas = CSendAs::NewL(observer);
    CleanupStack::PushL(sendas);

    sendas->SetMtmL(KUidMsgTypeMultimedia); // MMS type -  KUidMsgTypeMMS?
    sendas->SetService(0); // first and only MMS service? is this needed at all?
    sendas->CreateMessageL();

    TPtrC item;
    PyObject* s;
    int i, len;
    len = PySequence_Size(addrs);
    for (i = 0; i < len; i++) {
        s = PySequence_Fast_GET_ITEM(addrs, i);
        item.Set((TUint16*) PyUnicode_AS_DATA(s), PyUnicode_GET_SIZE(s));
        sendas->AddRecipientL(item);
    }
    sendas->SetSubjectL(msg_desc);

    TMsvId attachmentId;

    CMmsClientMtm& mtm = (CMmsClientMtm&)sendas->ClientMtm();
    len = PySequence_Size(files);
    for (i = 0; i < len; i++) {
        s = PySequence_Fast_GET_ITEM(files, i);
        item.Set((TUint16*) PyUnicode_AS_DATA(s), PyUnicode_GET_SIZE(s));
        attachmentId = i;
        mtm.CreateAttachment2L(attachmentId, item);
    }

    TMsvPartList partlist = sendas->ValidateMessage();
    if (partlist != 0)
    {   
        // msg invalid
        // set exception 
        PyErr_SetString(PyExc_SystemError, "ValidateMessage failed"); 
        CleanupStack::PopAndDestroy(sendas); 
        return NULL;
    }

    sendas->SaveMessageL(ETrue);


// the following copied from Nokia example MMSDemo1Engine.cpp (MMSDemo1_v1_0.zip,
// Series 60 Developer Platform: MMSDemo1 Example v1.0, 03-Apr-2003):

    // Start sending the message via the Server MTM to the MMS server
    CMsvOperationWait* wait = CMsvOperationWait::NewLC(); // left in CS
    wait->iStatus = KRequestPending; 

    CMsvOperation* op = NULL;
    op = mtm.SendL( wait->iStatus );
    CleanupStack::PushL( op );
    wait->Start();

    // Added Py_BEGIN_ALLOW_THREADS/Py_END_ALLOW_THREADS according to advice from Jukka Laurila:
    // You should release the interpreter lock before entering the Active Scheduler and reacquire it 
    // when you return from it. Whenever you call CActiveScheduler::Start() in a Python extension you should do this.
    Py_BEGIN_ALLOW_THREADS
    CActiveScheduler::Start();
    Py_END_ALLOW_THREADS      

    // The following is to ignore the completion of other active objects. It is not
    // needed if the app has a command absorbing control.
    while( wait->iStatus.Int() == KRequestPending )
    {
        Py_BEGIN_ALLOW_THREADS
        CActiveScheduler::Start();
        Py_END_ALLOW_THREADS      
    }

    CleanupStack::PopAndDestroy(2); // op, wait
    CleanupStack::PopAndDestroy(sendas); 

    return Py_BuildValue("i", wait->iStatus.Int());
}


static const PyMethodDef Methods[] = {
    {"mms_send",        mms_send,       METH_VARARGS, "Send an MMS message."}
   ,{"mms_sendtomany",  mms_sendtomany, METH_VARARGS, "Send an MMS message to list of addresses by attaching a list of filenames."}
   ,{NULL, NULL, 0, NULL}        /* Sentinel */
};

#define PyMODINIT_FUNC extern "C" DL_EXPORT(void) // PyMODINIT_FUNC not defined in PyS60 ??

PyMODINIT_FUNC
initmmsmodule()
{
    Py_InitModule("mmsmodule", Methods);
}

GLDEF_C TInt E32Dll(TDllReason)
{
  return KErrNone;
}

