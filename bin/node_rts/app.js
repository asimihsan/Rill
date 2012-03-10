var express = require('express');
var app = express.createServer();
var io = require('socket.io').listen(app);
var zmq = require('zmq');
var request = require('request');
var logger = io.log;
var util = require('util');

app.listen(8081);
app.get('/', function (req, res) {
    res.sendfile(__dirname + '/index.html');
});
app.use("/js", express.static(__dirname + "/js"));
app.use("/js/libs", express.static(__dirname + "/js/libs"));
app.use("/css", express.static(__dirname + "/css"));

io.sockets.on('connection', function (socket)
{
    logger.info("received client connection, waiting for hostname selection.");
    socket.emit("hostname_selection", {});
    socket.on('hostname_selection', function(data)
    {
        logger.info(util.format("received hostname selection %s, will poll for services.", data));
        var hostname = JSON.parse(data);    
        logger.debug("hostname: " + hostname);
        var bindings = []
        request('http://127.0.0.1:10000/list_of_services', function (error, response, body)
        {
            logger.info("sent out poll for services.");
            if (!error && response.statusCode == 200)
            {
                var contents = JSON.parse(body);
                for (var parser in contents)
                {
                    if (parser.indexOf(hostname) != -1)
                    {
                        console.log(parser);
                        console.log(contents[parser]);
                        bindings.push(contents[parser]);
                    }
                }
            }
            console.log("bindings are: " + bindings);
            var subs = []
            for (var i = 0; i < bindings.length; i++)
            {
                var binding = bindings[i];
                var sub = zmq.socket('sub');
                console.log("binding is: " + binding);
                sub.connect(binding);
                sub.subscribe('');
                sub.setsockopt('hwm', 1000);
                sub.on('message', handle_zeromq_message);
                subs.push(sub);
            }

            function handle_zeromq_message(msg)
            {
                obj = JSON.parse(msg);
                socket.emit('log', { contents: obj.contents });
                //console.log(msg.toString()); 
            }

            socket.on('disconnect', function() {
                console.log("client disconnection");
                for (var i = 0; i < subs.length; i++)
                {
                    var sub = subs[i];
                    sub.setsockopt('linger', 0);
                    sub.close();
                }
            }); // on disconnection
        }); // request for list of services
    }); // on hostname selection
}); // on connection


