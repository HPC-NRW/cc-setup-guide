package main

import (
	"encoding/json"
	"fmt"
	lp "github.com/ClusterCockpit/cc-lib/v2/ccMessage"
	mp "github.com/ClusterCockpit/cc-lib/v2/messageProcessor"
	"os"
	"time"
)

type Input struct {
	Router  json.RawMessage `json:"router"`
	Metrics []struct {
		Name  string            `json:"name"`
		Unit  string            `json:"unit"`
		Value float64           `json:"value"`
		Tags  map[string]string `json:"tags"`
	} `json:"metrics"`
}

func main() {
	var x Input
	json.NewDecoder(os.Stdin).Decode(&x)
	p, e := mp.NewMessageProcessor()
	if e != nil {
		panic(e)
	}
	if e = p.FromConfigJSON(x.Router); e != nil {
		panic(e)
	}
	out := []map[string]any{}
	for _, f := range x.Metrics {
		m, e := lp.NewMetric(f.Name, f.Tags, map[string]string{"unit": f.Unit}, f.Value, time.Unix(1700000000, 0))
		if e != nil {
			panic(e)
		}
		v, e := p.ProcessMessage(m)
		o := map[string]any{"input": f.Name, "input_value": f.Value, "input_tags": f.Tags, "dropped": v == nil}
		if e != nil {
			o["error"] = e.Error()
		}
		if v != nil {
			o["output"] = fmt.Sprint(v)
			o["name"] = v.Name()
			o["value"], _ = v.GetField("value")
			o["unit"], _ = v.GetMeta("unit")
		}
		out = append(out, o)
	}
	json.NewEncoder(os.Stdout).Encode(out)
}
