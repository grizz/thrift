#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netdb.h>
#include <string.h>

#include "thrift.h"
#include "thrift_socket.h"
#include "thrift_framed.h"
#include "thrift_binary_protocol.h"
#include "thrudoc.h"

#define HOST "localhost"
#define PORT 9091

int main (int argc, char **argv)
{
    THRIFT_UNUSED_VAR (argc);
    THRIFT_UNUSED_VAR (argv);

    g_type_init ();

    ThriftSocket * socket = g_object_new (THRIFT_TYPE_SOCKET,
                                          "hostname", HOST,
                                          "port", PORT, 
                                          NULL);

    ThriftFramed * framed = g_object_new (THRIFT_TYPE_FRAMED,
                                          "transport", socket,
                                          NULL);

    // TODO: figure out why sending it as a property seg-faults
    ThriftBinaryProtocol * protocol = g_object_new (THRIFT_TYPE_BINARY_PROTOCOL, 
                                                    "transport", framed, 
                                                    NULL);

    ThriftThrudocClient * client = g_object_new (THRIFT_THRUDOC_TYPE_CLIENT,
                                                 "protocol", protocol, 
                                                 NULL);

    if (0)
    {
        GValue host_value;
        g_value_init (&host_value, G_TYPE_STRING);
        g_object_get_property (G_OBJECT (socket), "hostname", &host_value);

        GValue port_value;
        g_value_init (&port_value, G_TYPE_STRING);
        g_object_get_property (G_OBJECT (socket), "port", &port_value);

        fprintf (stderr, "socket: hostname=%s, port=%d\n", 
                 g_value_get_string (&host_value),
                 g_value_get_uint (&port_value));
    }

    GError * err = NULL;
    if (!thrift_transport_open (THRIFT_TRANSPORT (socket), &err))
    {
        fprintf (stderr, "failed to connect to host");
        exit (-1);
    }

    if (1)
    {
        unsigned int i;
        GPtrArray * _return;
        thrift_thrudoc_get_buckets (client, &_return, NULL);
        fprintf (stderr, "len: %d\n", _return->len);
        for (i = 0; i < _return->len; i++)
        {
            fprintf (stderr, "bucket(%d): %s\n", i, 
                     (char *)g_ptr_array_index (_return, i));
            g_free (g_ptr_array_index (_return, i));
        }
        g_ptr_array_free (_return, 1);
    }
    if (0)
    {
        gchar * _return;
        thrift_thrudoc_admin (client, &_return, "echo", "data", NULL);
        fprintf (stderr, "admin ('echo', 'data')=%s\n", _return);
    }
    if (1)
    {
        gchar * _return;
        thrift_thrudoc_put (client, "bucket", "key", "value", NULL);
        thrift_thrudoc_get (client, &_return, "bucket", "key", NULL);
        fprintf (stderr, "put/get ('bucket', 'key', 'value)=%s\n", _return);
        g_free (_return);
    }

    g_object_unref (socket);
    g_object_unref (framed);
    g_object_unref (protocol);
    g_object_unref (client);

    return 0;
}